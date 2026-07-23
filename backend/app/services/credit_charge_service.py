class CreditChargeService:
    COSTS = {"inspiration_chat": 1, "viral_analysis": 3}

    def estimate(self, business_type: str) -> int:
        if business_type not in self.COSTS:
            raise ValueError("unsupported business type")
        return self.COSTS[business_type]
