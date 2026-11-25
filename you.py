        if s_sqs:
            target_squads = s_sqs
        elif session_model.get("squad_name"):
            target_squads = [session_model.get("squad_name")]
        else:
            target_squads = current_squad
        s_mods = session_model.get("selected_models")
        if s_mods:
            target_models = s_mods
        elif session_model.get("model_name"):
            target_models = [session_model.get("model_name")]
        else:
            target_models = current_model
