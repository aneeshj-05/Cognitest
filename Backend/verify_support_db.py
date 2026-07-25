import sys
sys.path.append('.')
import asyncio
from src.config import prisma
from src.modules.support.schema import SupportTicketCreate
from src.modules.support.service import create_support_ticket

async def main():
    print("Connecting to Prisma...")
    await prisma.connect()
    
    print("Inserting a mock support ticket...")
    mock_ticket_data = SupportTicketCreate(
        subject="End-to-End Verification Ticket",
        category="bug",
        description="Verifying that support tickets are successfully persisted in the database."
    )
    
    # Use service to create support ticket
    ticket = await create_support_ticket(mock_ticket_data, user_id="verify-user-id")
    print(f"Ticket created successfully! ID: {ticket.id}, subject: '{ticket.subject}', category: '{ticket.category}'")
    
    # Query back from DB
    print("Querying ticket from database...")
    db_ticket = await prisma.supportticket.find_unique(where={"id": ticket.id})
    if db_ticket:
        print("Success! Found ticket in database:")
        print(f"  ID: {db_ticket.id}")
        print(f"  Subject: {db_ticket.subject}")
        print(f"  Category: {db_ticket.category}")
        print(f"  Description: {db_ticket.description}")
        print(f"  Status: {db_ticket.status}")
        print(f"  UserId: {db_ticket.userId}")
        print(f"  WorkspaceId: {db_ticket.workspaceId}")
        print(f"  CreatedAt: {db_ticket.createdAt}")
        print(f"  UpdatedAt: {db_ticket.updatedAt}")
        
        # Clean up
        print("Cleaning up database record...")
        await prisma.supportticket.delete(where={"id": ticket.id})
        print("Database record cleaned up successfully.")
    else:
        print("Error: Ticket could not be retrieved from database.")

    await prisma.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
