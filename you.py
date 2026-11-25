    if selected_models:
        s_mods = [str(m) for m in selected_models if m]
    elif primary_model:
        s_mods = [primary_model]
    else:
        s_mods = []
    if selected_squads:
        s_sqs = [str(s) for s in selected_squads if s]
    elif primary_squad:
        s_sqs = [primary_squad]
    else:
        s_sqs = []
