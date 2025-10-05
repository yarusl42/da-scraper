from dataclasses import dataclass

@dataclass
class ScrapeConfig:
    scroll_pause_sec: float = 0.5
    navigation_timeout_ms: int = 30000

