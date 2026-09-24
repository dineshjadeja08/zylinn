"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import api from "@/lib/api";

type Appointment = {
  appointment_uuid: string;
  customer_name: string;
  appointment_date: string;
  appointment_time: string;
  status: string;
};

export default function AppointmentsPage() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  const fetchAppointments = async () => {
    try {
      const res = await api.get("/appointments");
      setAppointments(res.data);
    } catch (error) {
      toast({ title: "Error", description: "Failed to fetch appointments", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppointments();
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Appointments</h1>
      
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {loading ? <p>Loading...</p> : appointments.map(appt => (
          <Card key={appt.appointment_uuid}>
            <CardHeader>
              <CardTitle>{appt.customer_name}</CardTitle>
            </CardHeader>
            <CardContent>
              <p>Date: {appt.appointment_date}</p>
              <p>Time: {appt.appointment_time}</p>
              <p className="mt-2 font-semibold">Status: {appt.status}</p>
            </CardContent>
          </Card>
        ))}
        {!loading && appointments.length === 0 && <p>No appointments found.</p>}
      </div>
    </div>
  );
}
