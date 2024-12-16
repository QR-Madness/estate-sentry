import secrets

from sqlalchemy import Column, Integer, String

from .base import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    username = Column(String, unique=True, nullable=False)
    auth_method = Column(String, nullable=False)
    pin = Column(Integer, nullable=True)
    password = Column(String, nullable=True)
    token = Column(String, nullable=True)
    additional_data_json = Column(String, nullable=True)

    def generate_token(self):
        """
        Generates a secure, random token and **assigns** it to the `token` attribute.

        This method uses the `secrets.token_urlsafe` function to create a secure
        random token with a length of 64 characters.

        The generated token is
        stored in the `token` attribute of the instance and returned.

        :return: A secure, randomly generated token.
        """
        self.token = secrets.token_urlsafe(64)
        return self.token

    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, email={self.username})>"

