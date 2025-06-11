from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class JobDetail:
    """
    Data class representing detailed information for a Google Career job listing.
    """
    id: str
    title: str
    link: str
    minimum_qualifications: List[str] = field(default_factory=list)
    preferred_qualifications: List[str] = field(default_factory=list)
    about_the_job: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    recommend: Optional[int] = None
    analysis: Optional[str] = None

    @classmethod
    def from_meta(cls, meta: dict) -> "JobDetail":
        """Create a JobDetail with only id/title/link from meta dict."""
        return cls(id=meta['id'], title=meta['title'], link=meta['link'])

    @classmethod
    def from_sections(cls, job_detail: "JobDetail", sections: dict, recommend: int = None, analysis: str = None) -> "JobDetail":
        """
        Populate sections into an existing JobDetail instance.
        """
        job_detail.minimum_qualifications = sections.get('Minimum qualifications', [])
        job_detail.preferred_qualifications = sections.get('Preferred qualifications', [])
        job_detail.about_the_job = sections.get('About the job', [])
        job_detail.responsibilities = sections.get('Responsibilities', [])
        job_detail.recommend = recommend
        job_detail.analysis = analysis
        return job_detail

    def to_dict(self) -> dict:
        """Serialize JobDetail to JSON-friendly dict."""
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "minimum_qualifications": self.minimum_qualifications,
            "preferred_qualifications": self.preferred_qualifications,
            "about_the_job": self.about_the_job,
            "responsibilities": self.responsibilities,
            "recommend": self.recommend,
            "analysis": self.analysis,
        }
