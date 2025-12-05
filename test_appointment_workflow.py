"""
Test Appointment Booking Workflow
Tests the complete flow: LLM tool call -> database save -> API retrieval
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from adapters.llm_adapter import create_llm_adapter, get_system_prompt, BOOKING_TOOL
from models import (
    DatabaseManager,
    create_call_record,
    create_appointment_record,
    get_appointments_for_call,
    get_all_appointments
)

async def test_appointment_workflow():
    """Test the complete appointment booking workflow"""
    print("🧪 Testing Appointment Booking Workflow\n")
    
    # Setup
    import time
    call_id = f"test-appointment-{int(time.time())}"
    db_manager = DatabaseManager()
    db_manager.create_tables()
    
    # Create call record
    session = db_manager.get_session()
    try:
        call = create_call_record(
            session,
            call_id=call_id,
            room_name="test-room",
            agent_identity="test-agent"
        )
        print(f"✅ Created call record: {call.call_id}\n")
    finally:
        session.close()
    
    # Test 1: LLM with booking tool
    print("📞 Test 1: LLM generates tool call for appointment booking")
    print("-" * 60)
    
    llm_adapter = create_llm_adapter(call_id, use_mock=False)
    system_prompt = get_system_prompt("appointment")
    
    # Simulate a conversation where user provides all details
    conversation = """
    User: Hi, I'd like to book an appointment
    Agent: Hello! I'd be happy to help you book an appointment. May I have your name please?
    User: My name is John Smith
    Agent: Thank you, John. What date would you like for your appointment?
    User: How about March 15th, 2024?
    Agent: March 15th, 2024 works! What time would be best for you?
    User: 2:30 PM would be perfect
    Agent: Great! Is this for a general consultation or a specific service?
    User: It's for a general consultation
    Agent: Perfect! Let me confirm the details:
    - Name: John Smith
    - Date: March 15th, 2024 (2024-03-15)
    - Time: 2:30 PM
    - Service: General Consultation
    
    User: Yes, that's correct. Please book it.
    """
    
    prompt = f"{conversation}\n\nThe user has confirmed all details. Book the appointment now."
    
    try:
        result = await llm_adapter.generate_with_tools(
            prompt=prompt,
            system_prompt=system_prompt,
            tools=[BOOKING_TOOL]
        )
        
        print(f"Response: {result['text']}")
        print(f"Tool calls: {len(result['tool_calls'])}")
        
        if result['tool_calls']:
            for i, tool_call in enumerate(result['tool_calls'], 1):
                print(f"\n🔧 Tool Call {i}:")
                print(f"   Name: {tool_call['name']}")
                print(f"   Arguments: {tool_call['arguments']}")
                
                # Test 2: Create appointment in database
                print(f"\n📊 Test 2: Creating appointment in database")
                print("-" * 60)
                
                session = db_manager.get_session()
                try:
                    args = tool_call['arguments']
                    appointment = create_appointment_record(
                        session=session,
                        call_id=call_id,
                        customer_name=args['customer_name'],
                        appointment_date=args['appointment_date'],
                        appointment_time=args['appointment_time'],
                        customer_phone=args.get('customer_phone'),
                        customer_email=args.get('customer_email'),
                        service_type=args.get('service_type'),
                        notes=args.get('notes')
                    )
                    
                    print(f"✅ Appointment created with ID: {appointment.id}")
                    print(f"   Customer: {appointment.customer_name}")
                    print(f"   Date: {appointment.appointment_date}")
                    print(f"   Time: {appointment.appointment_time}")
                    print(f"   Service: {appointment.service_type}")
                    print(f"   Status: {appointment.status}")
                    
                finally:
                    session.close()
        else:
            print("⚠️  No tool calls generated (LLM may need clearer instructions)")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Retrieve appointments
    print(f"\n📋 Test 3: Retrieving appointments from database")
    print("-" * 60)
    
    session = db_manager.get_session()
    try:
        # Get appointments for this call
        call_appointments = get_appointments_for_call(session, call_id)
        print(f"Appointments for call {call_id}: {len(call_appointments)}")
        
        for appt in call_appointments:
            print(f"\n  📅 Appointment #{appt.id}")
            print(f"     Customer: {appt.customer_name}")
            print(f"     Date/Time: {appt.appointment_date} at {appt.appointment_time}")
            print(f"     Service: {appt.service_type}")
            print(f"     Status: {appt.status}")
        
        # Get all appointments
        all_appointments = get_all_appointments(session)
        print(f"\n📊 Total appointments in database: {len(all_appointments)}")
        
    finally:
        session.close()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(test_appointment_workflow())
