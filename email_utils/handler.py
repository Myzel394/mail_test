import binascii
from mailbox import Message
from typing import Union

from aiosmtpd.smtp import Envelope
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session
from sqlalchemy.sql import Alias

from app import logger
from app.controllers import global_settings as settings
from app.controllers.email_report import create_email_report
from app.controllers import server_statistics
from app.controllers.reserved_alias import get_reserved_alias_by_address
from app.database.dependencies import with_db
from app.email_report_data import EmailReportData
from app.models import LanguageType, ReservedAlias
from app.utils.email import normalize_email
from email_utils import status
from email_utils.errors import AliasNotFoundError, AliasNotYoursError, EmailHandlerError
from email_utils.html_handler import (
    convert_images, expand_shortened_urls, remove_single_pixel_image_trackers,
)
from email_utils.send_mail import (
    send_bounce_mail, send_error_mail, send_mail,
)
from email_utils.utils import (
    get_alias_from_user, extract_alias_address, generate_message_id, get_alias_by_email,
    get_header_unicode, get_email_by_from,
)
from email_utils.validators import validate_alias
from . import headers
from .bounce_messages import (
    extract_forward_status, extract_forward_status_header, generate_forward_status,
    get_report_from_message, is_not_deliverable, StatusType,
)
from .headers import set_header

__all__ = [
    "handle",
]


def get_alias(db: Session, /, local: str, domain: str) -> Union[Alias, ReservedAlias, None]:
    # Try reserved alias
    try:
        return get_reserved_alias_by_address(db, local=local, domain=domain)
    except NoResultFound:
        pass


async def handle(envelope: Envelope, message: Message) -> str:
    logger.info("Retrieving mail from database.")

    with with_db() as db:
        enable_image_proxy = settings.get(db, "ENABLE_IMAGE_PROXY")
        user = None

        try:
            message_id = generate_message_id()
            set_header(message, headers.MESSAGE_ID, message_id)

            logger.info("Checking if mail is a bounce mail from us.")
            if (report_message := get_report_from_message(message)) is not None:
                if (forward_status := extract_forward_status_header(report_message)) is not None:
                    logger.info("Mail is a bounce mail from us. Extracting data.")

                    try:
                        data = extract_forward_status(forward_status)
                    except (ValueError, binascii.Error):
                        logger.info("Forward status is invalid. Ignoring mail.")
                        return status.E200

                    logger.info(f"Data is {data=}.")

                    if data["status_type"] == StatusType.FORWARD_ALIAS_TO_OUTSIDE:
                        logger.info(
                            "Mail should originally be forwarded FROM a local alias TO the outside. "
                            "Informing local user."
                        )

                        try:
                            alias = get_alias_by_email(db, envelope.rcpt_tos[0])
                        except NoResultFound:
                            logger.info("Alias does not exist. We can't inform the user.")
                            return status.E200

                        logger.info("Alias exists. Informing user.")
                        send_bounce_mail(
                            data["outside_address"],
                            alias.user.email.address,
                            language=alias.user.language,
                        )

                        return status.E200
                    elif data["status_type"] == StatusType.FORWARD_OUTSIDE_TO_ALIAS:
                        logger.info(
                            "Mail should originally be forwarded FROM the outside TO a local alias. "
                            "Informing outside user."
                        )

                        send_bounce_mail(
                            envelope.rcpt_tos[0],
                            data["outside_address"],
                        )

                        return status.E200
                    elif data["status_type"] == StatusType.BOUNCE:
                        logger.info("Mail is a bounce mail from us. Nothing to do.")

                        return status.E200
                    elif data["status_type"] == StatusType.OFFICIAL:
                        # Todo: Inform admins
                        return status.E200

            logger.info("Checking if mail is a normal bounce mail.")
            if is_not_deliverable(envelope, message):
                logger.info("Mail is a bounce mail. No further action required.")
                return status.E200

            logger.info(
                f"Checking if DESTINATION mail {envelope.rcpt_tos[0]} is a relay address."
            )

            if (result := extract_alias_address(envelope.rcpt_tos[0])) is not None:
                # LOCALLY saved user wants to send a mail FROM alias TO the outside.
                alias_address, target = result
                from_mail = await normalize_email(envelope.mail_from)
                logger.info(
                    f"{envelope.rcpt_tos[0]} is an forward alias address (LOCAL wants to send to "
                    f"OUTSIDE). It should be sent to {target} via alias {alias_address} "
                    f"Checking if FROM {from_mail} user owns it."
                )

                try:
                    email = get_email_by_from(db, from_mail)
                except NoResultFound:
                    logger.info(f"User does not exist. Raising error.")
                    # Return "AliasNotYoursError" to avoid an alias being leaked
                    raise AliasNotYoursError()

                logger.info(f"Checking if user owns the given alias.")
                user = email.user

                local, domain = alias_address.split("@")

                if (alias := get_reserved_alias_by_address(db, local, domain)) is not None:
                    logger.info("Alias is a reserved alias.")

                    # Reserved alias
                    if user not in alias.users:
                        logger.info("User is not in reserved alias users. Raising error.")
                        raise AliasNotYoursError()
                else:
                    # Local alias
                    try:
                        alias = get_alias_from_user(db, user, local=local, domain=domain)
                    except NoResultFound:
                        logger.info("Alias does not exist. Raising error.")
                        raise AliasNotYoursError()

                logger.info("User owns the alias. Checking if alias is valid.")
                validate_alias(alias)
                logger.info("Alias is valid.")

                logger.info(
                    f"Local mail {alias.address} should be relayed to outside mail {target}. "
                    f"Sending email now..."
                )

                set_header(
                    message,
                    headers.KLECK_FORWARD_STATUS,
                    generate_forward_status(
                        StatusType.FORWARD_ALIAS_TO_OUTSIDE,
                        outside_address=target,
                        message_id=message_id,
                    )
                )

                send_mail(
                    message,
                    from_mail=alias.address,
                    to_mail=target,
                )
                server_statistics.add_sent_email(db)

                logger.info("Returning success back.")
                return status.E200

            logger.info(
                f"Checking if DESTINATION mail {envelope.rcpt_tos[0]} is an alias mail."
            )

            if alias := get_alias_by_email(db, email=envelope.rcpt_tos[0]):
                logger.info("Mail is an alias mail (OUTSIDE wants to send to LOCAL).")
                user = alias.user

                logger.info("Checking if alias is valid.")
                # OUTSIDE user wants to send a mail TO a locally saved user's private mail.
                validate_alias(alias)
                logger.info("Alias is valid.")

                report = EmailReportData(
                    mail_from=envelope.mail_from,
                    mail_to=alias.address,
                    subject=get_header_unicode(message[headers.SUBJECT]),
                    message_id=message[headers.MESSAGE_ID],
                )

                content = message.get_payload()

                if type(content) is list:
                    # Find html part
                    for part in content:
                        if part.get_content_type() == "text/html":
                            content = part.get_payload()
                            break
                    else:
                        # No html part found
                        content = None

                if content is not None:
                    if alias.remove_trackers:
                        content = remove_single_pixel_image_trackers(report, html=content)

                    if enable_image_proxy and alias.proxy_images:
                        content = convert_images(db, report, alias=alias, html=content)

                    if alias.expand_url_shorteners:
                        content = expand_shortened_urls(report, alias=alias, html=content)

                    server_statistics.add_removed_trackers(db, len(report.single_pixel_images))
                    server_statistics.add_proxied_images(db, len(report.proxied_images))
                    server_statistics.add_expanded_urls(db, len(report.expanded_urls))

                    message.set_payload(content, "utf-8")

                if alias.create_mail_report and alias.user.public_key is not None:
                    create_email_report(
                        db,
                        report_data=report,
                        user=alias.user,
                    )

                logger.info(
                    f"Email {envelope.mail_from} is from outside and wants to send to alias "
                    f"{alias.address}. "
                    f"Relaying email to locally saved user {alias.user.email.address}."
                )

                set_header(
                    message,
                    headers.KLECK_FORWARD_STATUS,
                    generate_forward_status(
                        StatusType.FORWARD_OUTSIDE_TO_ALIAS,
                        outside_address=envelope.mail_from,
                        message_id=message_id,
                    )
                )

                send_mail(
                    message,
                    from_mail=alias.create_outside_email(envelope.mail_from),
                    from_name=envelope.mail_from,
                    to_mail=alias.user.email.address,
                )
                server_statistics.add_sent_email(db)

                return status.E200

            logger.info(
                f"Checking if DESTINATION mail {envelope.rcpt_tos[0]} is an reserved alias mail."
            )
            local, domain = envelope.rcpt_tos[0].split("@")
            if reserved_alias := get_reserved_alias_by_address(db, local=local, domain=domain):
                # OUTSIDE user wants to send a mail TO a reserved alias.
                validate_alias(reserved_alias)

                set_header(
                    message,
                    headers.KLECK_FORWARD_STATUS,
                    generate_forward_status(
                        StatusType.OFFICIAL,
                        outside_address=envelope.mail_from,
                        message_id=message_id,
                    )
                )

                for user in reserved_alias.users:
                    send_mail(
                        message,
                        from_mail=reserved_alias.create_outside_email(envelope.mail_from),
                        from_name=envelope.mail_from,
                        to_mail=user.email.address,
                    )
                server_statistics.add_sent_email(db)

                return status.E200

            logger.info(
                f"Mail {envelope.mail_from} is neither a locally saved user nor does it want to "
                f"send to one. Sending error mail back."
            )
            raise AliasNotFoundError(status_code=status.E515)
        except EmailHandlerError as error:
            send_error_mail(
                from_mail=envelope.mail_from,
                targeted_mail=envelope.rcpt_tos[0],
                error=error,
                language=user.language if user is not None else LanguageType.EN_US,
            )

            return error.status_code
