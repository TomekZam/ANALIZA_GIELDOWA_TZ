# analysis/calculated_indicators/base.py

class CalculatedIndicator:
    """
    Bazowa klasa dla wskaźników wyliczanych lokalnie.

    Kontrakt:
    - prices_df     : dane cenowe (zawsze dostępne)
    - indicators_df : inne wskaźniki (opcjonalne, dla wskaźników zależnych)
    """

    code: str
    lookback_days: int | None = None

    # Informacyjnie – jakie inne wskaźniki są wymagane
    # (na razie NIE używane automatycznie)
    required_indicators: list[str] = []

    @property
    def indicator_family(self) -> str:
        """
        Semantyka wskaźnika:
        - fut_*  -> future (0 jest istotną wartością)
        - inne   -> calculated (0 = brak sygnału)
        """
        if self.code.startswith("fut_"):
            return "future"
        return "calculated"

    def compute(self, prices_df, indicators_df=None):
        raise NotImplementedError

