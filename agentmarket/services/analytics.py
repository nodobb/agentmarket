"""
Analytics and Tracking Service
"""

from datetime import datetime
from sqlalchemy.orm import Session
from agentmarket.models.database import Analytics
from agentmarket.models import get_db_dependency
from agentmarket.utils.config import settings


class AnalyticsService:
    """Service for tracking and analyzing platform usage"""
    
    def __init__(self):
        self.enabled = settings.ANALYTICS_ENABLED
    
    async def track_request(
        self,
        method: str,
        path: str,
        status_code: int,
        response_time: float,
        user_agent: str = "",
        ip_address: str = "unknown",
        agent_id: int = None,
        vendor_id: int = None,
        revenue: float = 0.0
    ):
        """Track an API request"""
        
        if not self.enabled:
            return
        
        # Get database session (simplified - in production use dependency injection)
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            engine = create_engine(settings.DATABASE_URL)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            db = SessionLocal()
            
            analytics_entry = Analytics(
                method=method,
                path=path,
                status_code=status_code,
                response_time=response_time,
                user_agent=user_agent[:500],  # Truncate long user agents
                ip_address=ip_address,
                agent_id=agent_id,
                vendor_id=vendor_id,
                revenue=revenue
            )
            
            db.add(analytics_entry)
            db.commit()
            db.close()
            
        except Exception as e:
            # Don't let analytics failures break the application
            print(f"Analytics tracking failed: {e}")
    
    def get_usage_stats(self, db: Session, days: int = 30):
        """Get platform usage statistics"""
        
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Basic request stats
        total_requests = db.query(Analytics).filter(
            Analytics.timestamp >= cutoff_date
        ).count()
        
        # Unique agents
        unique_agents = db.query(Analytics.agent_id).filter(
            Analytics.timestamp >= cutoff_date,
            Analytics.agent_id.isnot(None)
        ).distinct().count()
        
        # Revenue
        total_revenue = db.query(func.sum(Analytics.revenue)).filter(
            Analytics.timestamp >= cutoff_date
        ).scalar() or 0.0
        
        # Top endpoints
        top_endpoints = db.query(
            Analytics.path,
            func.count(Analytics.id).label('count')
        ).filter(
            Analytics.timestamp >= cutoff_date
        ).group_by(Analytics.path).order_by(func.count(Analytics.id).desc()).limit(10).all()
        
        return {
            "period_days": days,
            "total_requests": total_requests,
            "unique_agents": unique_agents,
            "total_revenue": float(total_revenue),
            "top_endpoints": [{"path": path, "count": count} for path, count in top_endpoints]
        }