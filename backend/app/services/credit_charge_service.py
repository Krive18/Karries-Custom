class CreditChargeService:
    VIRAL_VISUAL_PREMIUM_GOALS = frozenset({"setting", "lighting"})
    VIRAL_VISUAL_PREMIUM_COST = 20

    COSTS = {
        "inspiration_chat": 0,
        "inspiration_chat_pro": 5,
        "viral_analysis": 100,
        "video_production": 140,
        "ai_translation_delivery": 60,
        "omni_video_generation": 40,
        "omni_agent_image": 30,
        "scheduled_publish": 20,
    }

    def estimate(self, business_type: str) -> int:
        if business_type not in self.COSTS:
            raise ValueError("unsupported business type")
        return self.COSTS[business_type]

    def estimate_viral_analysis(self, analysis_goals: list[str]) -> int:
        base_cost = self.estimate("viral_analysis")
        normalized_goals = {str(goal).strip().lower() for goal in analysis_goals}
        if normalized_goals & self.VIRAL_VISUAL_PREMIUM_GOALS:
            return base_cost + self.VIRAL_VISUAL_PREMIUM_COST
        return base_cost
