
def has_discord_role(author, role) -> bool:
    roles = [x.name.upper() for x in author.roles]
    match_role = role if not role == "BOT" else "ADC"
    if not any(x.startswith(match_role) for x in roles):
        return False
    return True
