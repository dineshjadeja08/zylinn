"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import api from "@/lib/api";

type UsageData = {
  current_plan: string;
  calls_made: number;
  minutes_used: number;
};

export default function BillingPage() {
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  const fetchUsage = async () => {
    try {
      const res = await api.get("/billing/usage");
      setUsage(res.data);
    } catch (error) {
      toast({ title: "Error", description: "Failed to fetch billing usage", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsage();
  }, []);

  const handleUpgrade = async () => {
    try {
      const res = await api.post("/billing/subscribe", { plan_id: "pro" });
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url;
      }
    } catch (error) {
      toast({ title: "Error", description: "Failed to upgrade", variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Billing & Usage</h1>
      
      {loading ? (
        <p>Loading...</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Current Plan: {usage?.current_plan}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p>Calls Made: {usage?.calls_made}</p>
              <p>Minutes Used: {usage?.minutes_used}</p>
              <Button onClick={handleUpgrade} className="w-full">Upgrade to Pro</Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
