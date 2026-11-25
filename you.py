    if matched:
        active_squads = matched
    elif squad_list:
        active_squads = [squad_list[0]["squad_name"]]
    else:
        active_squads = []
