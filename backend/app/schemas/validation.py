from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field





class CreateTaskArgs(BaseModel):
    project_name: str = Field(..., description="Name of the project")
    task_name: str = Field(..., description="Name of the task to create")
    description: Optional[str] = None
    assignee_name: Optional[str] = Field(
        None, description="Name of the person to assign"
    )
    due_date: Optional[str] = Field(None, description="Due date in MM-DD-YYYY")
    priority: Optional[str] = Field(
        None, description="Priority level (e.g., Low, Medium, High)"
    )


class UpdateTaskArgs(BaseModel):
    project_name: str = Field(..., description="Name of the project")
    task_name: str = Field(..., description="Name of the task to update")
    new_name: Optional[str] = Field(None, description="New name for the task")
    status: Optional[str] = Field(None, description="Status (e.g., Open, Closed)")
    assignee_name: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = Field(
        None, description="Priority level (e.g., Low, Medium, High)"
    )


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
