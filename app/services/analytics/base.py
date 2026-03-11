from datetime import datetime, timedelta

class BaseAnalyticsService:
    @staticmethod
    def parse_period(period: str) -> int:
        mapping = {
            "7d": 7, "weekly": 7,
            "30d": 30, "monthly": 30,
            "90d": 90, "quarterly": 90,
            "365d": 365, "yearly": 365
        }
        return mapping.get(period.lower(), 30)

    @staticmethod
    def calculate_trend(current: float, previous: float) -> tuple[float, str]:
        if previous == 0:
            return (0.0, "neutral" if current == 0 else "up")
        
        change = ((current - previous) / previous) * 100
        
        if change > 0:
            status = "up"
        elif change < 0:
            status = "down"
        else:
            status = "neutral"
            
        return (round(change, 2), status)
        
    @staticmethod
    def format_kpi_card(value: float, current: float, previous: float) -> dict:
        trend, status = BaseAnalyticsService.calculate_trend(current, previous)
        return {
            "value": value,
            "trend_percentage": trend,
            "status": status
        }
