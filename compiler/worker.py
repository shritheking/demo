import time

def run_worker():
    """
    Polls the database for pending compile jobs and processes them using compile.py.
    """
    print("Starting background worker for compile jobs...")
    while True:
        # TODO: Query database for compile_jobs where status='pending'
        # For each job:
        #   Update status to 'processing'
        #   Call compile_ea()
        #   Upload to Supabase Storage
        #   Notify via Telegram
        #   Update status to 'completed'
        time.sleep(5)

if __name__ == "__main__":
    run_worker()
