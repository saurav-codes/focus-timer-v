


class ProductivityTechniques:
    """Constants for different productivity techniques."""
    TIME_BLOCKING = "time_blocking"
    TWO_MINUTE_RULE = "two_minute_rule"
    POMODORO = "pomodoro"
    DEEP_WORK = "deep_work"
    PARETO_PRINCIPLE = "pareto_principle"
    SINGLE_TASKING = "single_tasking"
    EAT_THE_FROG = "eat_the_frog"
    REGULAR_BREAKS = "regular_breaks"

    @classmethod
    def get_str(cls) -> str:
        return ", ".join([
            ProductivityTechniques.TIME_BLOCKING,
            ProductivityTechniques.TWO_MINUTE_RULE,
            ProductivityTechniques.POMODORO,
            ProductivityTechniques.DEEP_WORK,
            ProductivityTechniques.PARETO_PRINCIPLE,
            ProductivityTechniques.SINGLE_TASKING,
            ProductivityTechniques.EAT_THE_FROG,
            ProductivityTechniques.REGULAR_BREAKS,
        ])
    
    @classmethod
    def get_list(cls):
        return [
            ProductivityTechniques.TIME_BLOCKING,
            ProductivityTechniques.TWO_MINUTE_RULE,
            ProductivityTechniques.POMODORO,
            ProductivityTechniques.DEEP_WORK,
            ProductivityTechniques.PARETO_PRINCIPLE,
            ProductivityTechniques.SINGLE_TASKING,
            ProductivityTechniques.EAT_THE_FROG,
            ProductivityTechniques.REGULAR_BREAKS,
        ]
    
    @classmethod
    def get_list_dict(cls) -> list[dict[str, str]]:
        techniques_list = []
        for technique in cls.get_list():
            techniques_list.append({
                "value": technique,
                "label": technique.replace("_", " ").title()
            })
        return techniques_list




