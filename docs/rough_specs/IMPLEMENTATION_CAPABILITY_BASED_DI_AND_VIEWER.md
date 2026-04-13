Goal
Implement endpoint-level scoped capabilities instead of full DAL injection.
Automatically generate a simple viewer that lists every endpoint and exactly which capabilities it receives (with change detection for PR reviews).
Core Security Idea
Instead of:
Python# BAD – too powerful
def create_project(dal: ProjectsDAL = Depends(...))
Do this:
Python# GOOD – least privilege
def create_project(projects_write: ProjectsWriteOnlyCapability = Depends(...))
Step-by-Step Implementation

Create folder: backend/capabilities/
Capability Example (backend/capabilities/projects_write_capability.py)Pythonclass ProjectsWriteOnlyCapability:
    def __init__(self, dal, current_user):
        self.dal = dal
        self.user = current_user

    def create(self, data):
        if not self.user.owns_project(data.org_id):
            raise PermissionError("Access denied")
        return self.dal.create(data)

def get_projects_write_capability(
    dal=Depends(get_projects_dal),
    user=Depends(get_current_user)
) -> ProjectsWriteOnlyCapability:
    return ProjectsWriteOnlyCapability(dal, user)
Update all routers to use the new scoped capabilities instead of full DALs.
Analyzer Script (tools/analyze_capabilities.py)
Introspects FastAPI routes
Extracts injected capabilities per endpoint
Compares to previous baseline
Flags any increase in access

Simple POC Capability Viewer (evidence/capabilities/index.html)
Table: Endpoint | Method | Capabilities list
Red highlight on any changed/increased capabilities
Diff column showing old → new
Same visual style as the evidence gallery


Acceptance Criteria for File 2

No endpoint receives a full DAL anymore
python tools/analyze_capabilities.py runs cleanly and produces a report
Viewer shows clear list + change detection
Can be used in GitHub Action to post: "⚠️ Capability Change Detected"


Final Notes for All Agents

Keep both viewers minimal and static for the POC
Make everything runnable with simple commands
Add clear comments so future AI agents understand the conventions
Prioritize File 1 first (higher visual impact for the blog post)
