from fastapi import Header, HTTPException, status


def require_roles(*allowed_roles: str):
    def dependency(role: str | None = Header(default=None, alias="X-Role")) -> str:
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cabecalho X-Role obrigatorio",
            )

        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissao insuficiente",
            )

        return role

    return dependency
