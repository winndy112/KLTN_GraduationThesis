
import os
from app.database.mongo import db_ioc
from app.services.misp_service import MISPService

def check_db():
    svc = MISPService(db_ioc)
    print(f"Total events: {svc.col_events.count_documents({})}")
    
    # Print first 5 events to see structure
    for doc in svc.col_events.find().limit(5):
        print(f"ID: {doc.get('event_id')} (type: {type(doc.get('event_id'))})")

    # Try querying
    print("\nTesting query...")
    # Find one ID to test
    one = svc.col_events.find_one()
    if one:
        eid = one.get('event_id')
        print(f"Querying for ID: {eid}")
        results = svc.query_events({"event_id": eid})
        print(f"Found: {len(results)}")
        
        # Test string query if it was int
        if isinstance(eid, int):
            print(f"Querying with string '{eid}' (simulating frontend passing string but backend casting?)")
            # In python direct mongo query, type matters.
            # But via FastAPI, it casts.
            
            # Let's check if there are any string IDs
            str_ids = list(svc.col_events.find({"event_id": {"$type": "string"}}))
            print(f"Events with string ID: {len(str_ids)}")

if __name__ == "__main__":
    check_db()
