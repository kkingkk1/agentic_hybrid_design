"""Fixed-tenure move memory with incumbent-best aspiration."""


class TabuMemory:
    """Store per-attribute expiry iterations for minimization."""

    def __init__(self, tenure):
        if tenure < 0:
            raise ValueError("tenure must be nonnegative")
        self.tenure = tenure
        self.expiry = {}

    def permits(self, attribute, iteration, candidate_cost, best_cost):
        """Allow an expired move or one that strictly improves the best cost."""
        return iteration > self.expiry.get(attribute, -1) or candidate_cost < best_cost

    def forbid(self, attribute, iteration):
        """Mark the attribute tabu for the next tenure iterations."""
        self.expiry[attribute] = iteration + self.tenure
