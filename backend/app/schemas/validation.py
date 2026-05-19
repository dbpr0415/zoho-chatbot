from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum

class PriorityEnum(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"

class StatusEnum(str, Enum):
    open = "Open"
    closed = "Closed"

class CreateTaskArgs(BaseModel):
    project_name: str = Field(..., description="Name of the project")
    task_name: str = Field(..., description="Name of the task to create")
    description: Optional[str] = None
    assignee_name: Optional[str] = Field(None, description="Name of the person to assign")
    due_date: Optional[str] = Field(None, description="Due date in MM-DD-YYYY")
    priority: Optional[PriorityEnum] = None

class UpdateTaskArgs(BaseModel):
    project_name: str = Field(..., description="Name of the project")
    task_name: str = Field(..., description="Name of the task to update")
    new_name: Optional[str] = Field(None, description="New name for the task")
    status: Optional[StatusEnum] = None
    assignee_name: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[PriorityEnum] = None

class DeleteTaskArgs(BaseModel):
    project_name: str = Field(..., description="Name of the project")
    task_name: str = Field(..., description="Name of the task to delete")

class ProjectQueryArgs(BaseModel):
    project_name: str = Field(..., description="Name of the project")

class TaskQueryArgs(BaseModel):
    project_name: str = Field(..., description="Name of the project")
    status: Optional[str] = None
    assignee_name: Optional[str] = None

class TaskDetailsArgs(BaseModel):
    project_name: str = Field(..., description="Name of the project")
    task_name: str = Field(..., description="Name of the task")
