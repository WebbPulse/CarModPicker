from dataclasses import dataclass

from app.db.dynamo.users import OAuthAccountRepository, UserRepository, WebAuthnCredentialRepository


@dataclass(frozen=True)
class Repositories:
    users: UserRepository
    oauth_accounts: OAuthAccountRepository
    webauthn_credentials: WebAuthnCredentialRepository


_repositories = Repositories(
    users=UserRepository(),
    oauth_accounts=OAuthAccountRepository(),
    webauthn_credentials=WebAuthnCredentialRepository(),
)


def get_repositories() -> Repositories:
    return _repositories
