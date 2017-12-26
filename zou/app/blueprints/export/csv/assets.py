from flask_restful import Resource
from flask_jwt_extended import jwt_required

from zou.app.services import assets_service, user_service, projects_service
from zou.app.utils import csv_utils


class AssetsCsvExport(Resource):

    @jwt_required
    def get(self, project_id):
        project = projects_service.get_project(project_id)
        self.check_permissions(project["id"])

        csv_content = []
        results = self.get_assets_data(project_id)
        validation_columns = self.get_validation_columns(results)
        csv_content.append(self.build_headers(validation_columns))

        for result in results:
            result["project_name"] = project["name"]
            csv_content.append(self.build_row(result, validation_columns))

        file_name = "%s assets" % project["name"]
        return csv_utils.build_csv_response(csv_content, file_name)

    def check_permissions(self, project_id):
        user_service.check_project_access(project_id)

    def build_headers(self, validation_columns):
        headers = [
            "Project",
            "Type",
            "Name",
            "Description",
        ]
        return headers + validation_columns

    def build_row(self, result, validation_columns):
        row = [
            result["project_name"],
            result["asset_type_name"],
            result["name"],
            result["description"]
        ]
        task_map = {}
        for task in result["tasks"]:
            task_map[task["task_type_name"]] = task["task_status_short_name"]
        for column in validation_columns:
            row.append(task_map.get(column, ""))
        return row

    def get_assets_data(self, project_id):
        results = assets_service.all_assets_and_tasks({
            "project_id": project_id
        })
        return sorted(
            results,
            key=lambda asset: (asset["asset_type_name"], asset["name"])
        )

    def get_validation_columns(self, results):
        task_type_map = {}

        for result in results:
            for task in result["tasks"]:
                task_type_map[task["task_type_name"]] = {
                    "name": task["task_type_name"],
                    "priority": task["task_type_priority"]
                }

        validation_columns = [
            task_type["name"] for task_type in sorted(
                task_type_map.values(),
                key=lambda task_type: (task_type["priority"], task_type["name"])
            )
        ]

        return validation_columns
