"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import api from "@/lib/api";

type Call = {
  call_id: string;
  caller_number: string;
  duration_seconds: number;
  summary: string;
  status: string;
  created_at: string;
};

export default function CallsPage() {
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  const fetchCalls = async () => {
    try {
      const res = await api.get("/calls");
      setCalls(res.data);
    } catch (error) {
      toast({ title: "Error", description: "Failed to fetch calls", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCalls();
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Call History</h1>
      
      <div className="grid gap-4">
        {loading ? <p>Loading...</p> : calls.map(call => (
          <Card key={call.call_id}>
            <CardHeader>
              <CardTitle className="text-lg">Call from {call.caller_number}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4 text-sm text-gray-500 mb-2">
                <span>Duration: {call.duration_seconds}s</span>
                <span>Status: {call.status}</span>
                <span>Date: {new Date(call.created_at).toLocaleString()}</span>
              </div>
              <p className="text-sm mt-2">{call.summary}</p>
            </CardContent>
          </Card>
        ))}
        {!loading && calls.length === 0 && <p>No calls found.</p>}
      </div>
    </div>
  );
}
