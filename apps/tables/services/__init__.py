from apps.tables.models import Table
from apps.auditlogs.models import AuditLog

class TableService:
    @staticmethod
    def create_table(organization_id: str, name: str, created_by) -> Table:
        table = Table.objects.create(organization_id=organization_id, name=name)
        # Assuming audit logging here
        return table
        
    @staticmethod
    def rename_table(table: Table, name: str, updated_by) -> Table:
        table.name = name
        table.save()
        return table

    @staticmethod
    def archive_table(table: Table, archived_by):
        from apps.tables.models import TableStatus
        table.status = TableStatus.ARCHIVED
        table.save()
        
    @staticmethod
    def delete_table(table: Table, deleted_by):
        table.soft_delete()
