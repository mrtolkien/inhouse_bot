from sqlalchemy import Enum

roles_list = ["TOP", "JGL", "MID", "BOT", "SUP"]
role_enum = Enum(*roles_list, name="role_enum")

team_enum = Enum("blue", "red", name="team_enum")

foreignkey_cascade_options = {"onupdate": "CASCADE", "ondelete": "CASCADE"}
