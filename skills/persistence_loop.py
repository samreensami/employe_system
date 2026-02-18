import os
import time
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)


class PersistenceLoop:
    """
    Implements the Ralph Wiggum Loop - prevents terminal exit until all tasks
    are processed through the workflow pipeline.

    Monitors:
        - /Plans: Tasks awaiting human approval
        - /Approved: Tasks awaiting execution
        - /Pending_Approval/odoo: Odoo documents awaiting approval

    The loop ensures the agent stays alive while work is pending.
    """

    def __init__(
        self,
        plans_path: str = "obsidian_vault/Plans",
        approved_path: str = "obsidian_vault/Approved",
        pending_odoo_path: str = "obsidian_vault/Pending_Approval/odoo",
        done_path: str = "obsidian_vault/Done",
        check_interval: int = 5
    ):
        self.plans_path = Path(plans_path)
        self.approved_path = Path(approved_path)
        self.pending_odoo_path = Path(pending_odoo_path)
        self.done_path = Path(done_path)
        self.check_interval = check_interval
        self.active_tasks = set()
        self._stop_requested = False

        # Ensure directories exist
        for path in [self.plans_path, self.approved_path, self.pending_odoo_path, self.done_path]:
            path.mkdir(parents=True, exist_ok=True)

    def get_plan_files(self) -> list:
        """Get all plan files in the Plans folder."""
        if not self.plans_path.exists():
            return []
        return [f.name for f in self.plans_path.glob("PLAN_*.md")]

    def get_approved_files(self) -> list:
        """Get all files in the Approved folder awaiting execution."""
        if not self.approved_path.exists():
            return []
        return [f.name for f in self.approved_path.glob("*.md")]

    def get_pending_odoo_files(self) -> list:
        """Get all Odoo documents pending approval."""
        if not self.pending_odoo_path.exists():
            return []
        return [f.name for f in self.pending_odoo_path.glob("ODOO_*.md")]

    def get_all_pending_work(self) -> dict:
        """Get all pending work across all monitored folders."""
        return {
            'plans': self.get_plan_files(),
            'approved': self.get_approved_files(),
            'pending_odoo': self.get_pending_odoo_files()
        }

    def has_pending_work(self) -> bool:
        """Check if there is any pending work in the pipeline."""
        work = self.get_all_pending_work()
        return bool(work['plans'] or work['approved'] or work['pending_odoo'])

    def monitor_tasks(self, continuous: bool = False):
        """
        Monitor tasks until all are processed.

        Args:
            continuous: If True, never exit (for always-on operation).
                       If False, exit when no work pending.
        """
        print("\n" + "=" * 60)
        print("Ralph Wiggum Loop - Persistence Monitor")
        print("=" * 60)
        print(f"Monitoring folders:")
        print(f"  - Plans:          {self.plans_path}")
        print(f"  - Approved:       {self.approved_path}")
        print(f"  - Pending Odoo:   {self.pending_odoo_path}")
        print(f"  - Done:           {self.done_path}")
        print(f"Check interval: {self.check_interval} seconds")
        print("=" * 60 + "\n")

        logger.info("Ralph Wiggum Loop activated")

        iteration = 0
        while not self._stop_requested:
            iteration += 1
            work = self.get_all_pending_work()
            timestamp = datetime.now().strftime('%H:%M:%S')

            total_pending = len(work['plans']) + len(work['approved']) + len(work['pending_odoo'])

            if total_pending == 0:
                if continuous:
                    if iteration % 12 == 0:  # Log every minute (12 * 5 seconds)
                        print(f"[{timestamp}] No pending work - standing by...")
                        logger.debug("No pending work - standing by")
                else:
                    print(f"\n[{timestamp}] All tasks completed!")
                    print("=" * 40)
                    print("No active tasks in pipeline.")
                    print("Persistence loop terminating gracefully.")
                    print("=" * 40 + "\n")
                    logger.info("Ralph Wiggum Loop: All tasks completed, exiting")
                    break
            else:
                print(f"\n[{timestamp}] Pending Work Summary:")
                print("-" * 40)

                if work['plans']:
                    print(f"  Plans (awaiting approval): {len(work['plans'])}")
                    for f in work['plans'][:3]:  # Show first 3
                        print(f"    - {f}")
                    if len(work['plans']) > 3:
                        print(f"    ... and {len(work['plans']) - 3} more")

                if work['approved']:
                    print(f"  Approved (awaiting execution): {len(work['approved'])}")
                    for f in work['approved'][:3]:
                        print(f"    - {f}")
                    if len(work['approved']) > 3:
                        print(f"    ... and {len(work['approved']) - 3} more")

                if work['pending_odoo']:
                    print(f"  Pending Odoo (awaiting approval): {len(work['pending_odoo'])}")
                    for f in work['pending_odoo'][:3]:
                        print(f"    - {f}")
                    if len(work['pending_odoo']) > 3:
                        print(f"    ... and {len(work['pending_odoo']) - 3} more")

                print("-" * 40)
                print(f"  TOTAL PENDING: {total_pending}")

            # Wait before next check
            time.sleep(self.check_interval)

        return True

    def stop(self):
        """Request the loop to stop."""
        self._stop_requested = True
        logger.info("Ralph Wiggum Loop: Stop requested")

    def get_status(self) -> dict:
        """Get current loop status."""
        work = self.get_all_pending_work()
        return {
            'running': not self._stop_requested,
            'plans_pending': len(work['plans']),
            'approved_pending': len(work['approved']),
            'odoo_pending': len(work['pending_odoo']),
            'total_pending': len(work['plans']) + len(work['approved']) + len(work['pending_odoo']),
            'check_interval': self.check_interval
        }


def main():
    """Main function to run the persistence loop."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\nRalph Wiggum Loop - Standalone Mode")
    print("Press Ctrl+C to stop\n")

    loop = PersistenceLoop()

    try:
        loop.monitor_tasks(continuous=False)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        loop.stop()

    print("Ralph Wiggum Loop stopped")


if __name__ == "__main__":
    main()