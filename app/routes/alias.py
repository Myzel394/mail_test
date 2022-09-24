from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy.orm import Session

from app import logger
from app.authentication.handler import access_security
from app.authentication.user_management import get_user_by_id
from app.controllers.alias import (
    create_local_with_suffix, generate_random_local_id,
    get_alias_from_user,
)
from app.database.dependencies import get_db
from app.life_constants import MAIL_DOMAIN
from app.models.alias import AliasType, EmailAlias
from app.schemas._basic import HTTPNotFoundExceptionModel
from app.schemas.alias import Alias, AliasCreate, AliasUpdate

router = APIRouter()


@router.post(
    "/",
    response_model=Alias,
)
def create_alias(
    alias_data: AliasCreate,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    logger.info("Request: Create Alias -> Creating alias.")
    user = get_user_by_id(db, credentials["id"])

    if alias_data.type == AliasType.RANDOM:
        logger.info("Request: Create Alias -> Type is AliasType.RANDOM")
        local = generate_random_local_id(db, domain=MAIL_DOMAIN)
    else:
        logger.info("Request: Create Alias -> Type is AliasType.CUSTOM")
        local = create_local_with_suffix(db, domain=MAIL_DOMAIN, local=alias_data.local)

    logger.info(f"Request: Create Alias -> Creating email alias with local={local} and domain="
                f"{MAIL_DOMAIN} for {user.email.address}.")
    alias = EmailAlias(
        local=local,
        domain=MAIL_DOMAIN,
        is_active=alias_data.is_active,
        encrypted_notes=alias_data.encrypted_notes,
        type=alias_data.type,
        user=user,
    )

    logger.info("Request: Create Alias -> Saving instance.")
    db.add(alias)
    db.commit()
    db.refresh(alias)

    logger.info("Request: Create Alias -> Instance saved successfully.")
    return alias


@router.patch(
    "/{id}",
    response_model=Alias,
    responses={
        404: {
            "model": HTTPNotFoundExceptionModel
        }
    }
)
def update_alias(
    id: str,
    update: AliasUpdate,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    logger.info(f"Request: Update Alias -> Updating alias with id={id}.")
    user = get_user_by_id(db, credentials["id"])
    alias = get_alias_from_user(db, user=user, id=id)

    if alias is None:
        logger.info(f"Request: Update Alias -> Alias {id} not found.")
        raise HTTPException(
            status_code=404,
            detail="Alias not found."
        )

    logger.info(f"Request: Update Alias -> Updating values of Alias {id}.")
    update_data = update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(alias, key, value)

    logger.info(f"Request: Update Alias -> Saving Alias {id} to database.")
    db.add(alias)
    db.commit()
    db.refresh(alias)

    logger.info(f"Request: Update Alias -> Alias {id} saved successfully.")
    return alias

