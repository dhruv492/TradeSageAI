"""
Module      : auth_service.py
Date        : 2026-08-07
Author      : Dhruv
Modification History:
    2026-08-07 - Recreated (rebuild session). Implements FR-1.1-1.3.
Synopsis:
    Registration, login, and logout using Flask-Login for session
    management and werkzeug's password hashing (never plaintext, NFR-4).

Functions:
    registerUser(dbSession, email, plaintextPassword) -> User
        Raises ValueError if the email is already registered.
    verifyLogin(dbSession, email, plaintextPassword) -> User | None
        Returns the User row on success, None on bad credentials.
    loginUser(user) -> None      # thin wrapper over flask_login.login_user
    logoutUser() -> None         # thin wrapper over flask_login.logout_user

Globals accessed/modified: None.
"""

from flask_login import login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import User


def registerUser(dbSession, email, plaintextPassword):
    existingUser = dbSession.query(User).filter_by(email=email).first()
    if existingUser is not None:
        raise ValueError("email already registered")

    newUser = User(email=email, passwordHash=generate_password_hash(plaintextPassword))
    dbSession.add(newUser)
    dbSession.commit()
    return newUser


def verifyLogin(dbSession, email, plaintextPassword):
    user = dbSession.query(User).filter_by(email=email).first()
    if user is None or not check_password_hash(user.passwordHash, plaintextPassword):
        return None
    return user


def loginUser(user):
    login_user(user)


def logoutUser():
    logout_user()
