import time
from email import message_from_bytes
from mailbox import Message

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope

from app import logger
from app.database.dependencies import with_db
from email_utils import status
from email_utils.errors import EmailHandlerError
from email_utils.sanitizers import sanitize_envelope, sanitize_message
from email_utils.send_mail import (
    send_error_mail, send_mail_from_outside_to_private_mail,
    send_mail_from_private_mail_to_destination,
)
from email_utils.utils import get_alias_email, get_local_email


class ExampleHandler:
    def handle(self, envelope: Envelope, message: Message):
        logger.info("Retrieving mail from database.")

        with with_db() as db:
            logger.info(f"Checking if FROM mail {envelope.mail_from} is locally saved.")

            if email := get_local_email(db, email=envelope.mail_from):
                # LOCALLY saved user wants to send a mail FROM its private mail TO the outside.
                logger.info(
                    f"Mail {envelope.mail_from} is a locally saved user. Relaying mail to "
                    f"destination {envelope.rcpt_tos[0]}."
                )

                try:
                    send_mail_from_private_mail_to_destination(envelope, message, email)

                    return status.E200
                except EmailHandlerError as error:
                    send_error_mail(
                        error=error,
                        mail=envelope.mail_from,
                        targeted_mail=envelope.rcpt_tos[0],
                        language=email.user.language,
                    )

                    return status.E521

            logger.info(
                f"Checking if DESTINATION mail {envelope.rcpt_tos[0]} is an alias mail."
            )

            if alias := get_alias_email(db, email=envelope.rcpt_tos[0]):
                # OUTSIDE user wants to send a mail TO a locally saved user's private mail.
                logger.info(
                    f"Email {envelope.mail_from} is from outside and wants to send to alias "
                    f"{alias.address}. "
                    f"Relaying email to locally saved user {alias.user.email.address}."
                )
                try:
                    send_mail_from_outside_to_private_mail(envelope, message, alias)

                    return status.E200
                except EmailHandlerError as error:
                    send_error_mail(
                        error=error,
                        mail=envelope.mail_from,
                        targeted_mail=envelope.rcpt_tos[0],
                        language=email.user.language,
                    )

                    return status.E521

            logger.info(
                f"Mail {envelope.mail_from} is neither a locally saved user nor does it want to "
                f"send to one. Sending error mail back."
            )

            return status.E501

    async def handle_DATA(self, server, session, envelope: Envelope):
        logger.info("New DATA received. Validating data...")

        try:
            sanitize_envelope(envelope)

            message = message_from_bytes(envelope.original_content)
            sanitize_message(message)

            logger.info("Data validated successfully.")

            logger.info(f"New mail received from {envelope.mail_from} to {envelope.rcpt_tos[0]}")

            return self.handle(envelope, message)
        except Exception as error:
            send_error_mail(
                mail=envelope.mail_from,
                targeted_mail=envelope.rcpt_tos[0],
            )

            return status.E501


def main():
    controller = Controller(ExampleHandler(), hostname="0.0.0.0", port=20381)
    controller.start()

    while True:
        time.sleep(2)


if __name__ == "__main__":
    main()
