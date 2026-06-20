from datetime import datetime, timezone, timedelta

class EscalationAnalyticsEngine:
    def __init__(self):
        """
        Pure computational algorithmic engine mapped directly to the 
        provided PostgreSQL ER Diagram and workflow constraints.
        """
        pass

    # ==========================================
    # ANALYTICS ENGINE LOGIC
    # ==========================================
    def calculate_dashboard_metrics(self, complaints: list[dict]) -> dict:
        """
        Processes your raw 'complaints' table records to generate live analytics.
        Supports metrics visualization by aggregating status types and computing average SLA.
        """
        total_complaints = len(complaints)
        if total_complaints == 0:
            return {
                "total_count": 0, "pending_count": 0, "in_progress_count": 0,
                "resolved_count": 0, "escalated_count": 0, "average_sla_resolution_hours": 0.0
            }

        # Status count trackers based on your schema status_enum values
        status_counts = {"OPEN": 0, "IN_PROGRESS": 0, "RESOLVED": 0, "REJECTED": 0, "ESCALATED": 0}
        resolution_times = []

        for ticket in complaints:
            status = ticket.get("status", "OPEN").upper()
            if status in status_counts:
                status_counts[status] += 1
                
            # If the complaint is resolved, calculate resolution speed using timestamps from schema
            if status == "RESOLVED" and ticket.get("created_at") and ticket.get("updated_at"):
                try:
                    c_time = ticket["created_at"]
                    u_time = ticket["updated_at"]
                    
                    # Handle both datetime objects or ISO-string parsing safely
                    if isinstance(c_time, str):
                        c_time = datetime.fromisoformat(c_time.replace("Z", "+00:00"))
                    if isinstance(u_time, str):
                        u_time = datetime.fromisoformat(u_time.replace("Z", "+00:00"))
                        
                    duration = u_time - c_time
                    resolution_times.append(duration.total_seconds() / 3600.0) # convert to hours
                except Exception:
                    continue

        avg_sla = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0

        return {
            "total_count": total_complaints,
            "pending_count": status_counts["OPEN"],
            "in_progress_count": status_counts["IN_PROGRESS"],
            "resolved_count": status_counts["RESOLVED"],
            "escalated_count": status_counts["ESCALATED"],
            "rejected_count": status_counts["REJECTED"],
            "average_sla_resolution_hours": round(avg_sla, 2)
        }

    # ==========================================
    # AUTOMATED ESCALATION SERVICE LOGIC
    # ==========================================
    def process_delayed_escalations(
        self, 
        active_complaints: list[dict], 
        officers: list[dict], 
        departments: list[dict]
    ) -> dict:
        """
        Executes `/api/v1/escalations/run`.
        Implements Workflow Step 14: If OPEN/IN_PROGRESS > 72h -> Escalate to Department Head.
        
        Returns:
            dict containing:
              - 'updated_complaints': list of modified complaints with ESCALATED status.
              - 'new_escalation_records': list of records matching the 'escalations' schema table.
        """
        current_time = datetime.now(timezone.utc)
        sla_threshold_hours = 72
        
        updated_complaints = []
        new_escalation_records = []
        
        # Build quick-lookup maps from officers and departments arrays
        officer_map = {o["id"]: o for o in officers}
        dept_map = {d["id"]: d for d in departments}
        
        # Find department heads to handle escalations
        dept_heads = {}
        for o in officers:
            if o.get("designation", "").upper() == "HEAD":
                dept_heads[o["department_id"]] = o["id"]

        for ticket in active_complaints:
            # Only check non-final complaints
            if ticket.get("status") in ["RESOLVED", "REJECTED", "ESCALATED"]:
                continue
                
            c_time = ticket.get("created_at")
            if not c_time:
                continue
                
            if isinstance(c_time, str):
                c_time = datetime.fromisoformat(c_time.replace("Z", "+00:00"))
                
            # Compute age of complaint ticket
            age_hours = (current_time - c_time).total_seconds() / 3600.0
            
            if age_hours > sla_threshold_hours:
                # 1. Identify escalation path targeting the department head
                assigned_officer_id = ticket.get("assigned_to")
                dept_id = ticket.get("department_id")
                
                if assigned_officer_id and assigned_officer_id in officer_map:
                    dept_id = officer_map[assigned_officer_id]["department_id"]
                
                # Fallback to a default administrative entity ID if department head isn't explicitly found
                escalate_to_uid = dept_heads.get(dept_id, "SYSTEM_ADMIN_HEAD")
                
                # 2. Build updated state mutations for 'complaints' table
                modified_ticket = ticket.copy()
                modified_ticket["status"] = "ESCALATED"
                modified_ticket["updated_at"] = current_time
                updated_complaints.append(modified_ticket)
                
                # 3. Create entry matching your 'escalations' schema table structure
                escalation_entry = {
                    "complaint_id": ticket.get("id"),
                    "escalated_to": escalate_to_uid,
                    "reason": f"SLA breached. Complaint pending unresolved for {round(age_hours, 1)} hours.",
                    "is_resolved": False,
                    "resolved_at": None,
                    "created_at": current_time
                }
                new_escalation_records.append(escalation_entry)

        return {
            "updated_complaints": updated_complaints,
            "new_escalation_records": new_escalation_records
        }
