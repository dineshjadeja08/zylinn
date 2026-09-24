"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import api from "@/lib/api";

type AgentConfig = {
  id: string;
  name: string;
  language: string;
  voice_id: string;
  system_prompt: string;
  is_active: boolean;
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  const [form, setForm] = useState<Partial<AgentConfig>>({
    name: "",
    language: "en",
    voice_id: "",
    system_prompt: "",
    is_active: true,
  });

  const fetchAgents = async () => {
    try {
      const res = await api.get("/agents/");
      setAgents(res.data);
    } catch (error) {
      toast({ title: "Error", description: "Failed to fetch agents", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleSave = async () => {
    try {
      if (form.id) {
        await api.put(`/agents/${form.id}`, form);
      } else {
        await api.post("/agents/", form);
      }
      toast({ title: "Success", description: "Agent saved" });
      fetchAgents();
      setForm({ name: "", language: "en", voice_id: "", system_prompt: "", is_active: true });
    } catch (error) {
      toast({ title: "Error", description: "Failed to save agent", variant: "destructive" });
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/agents/${id}`);
      toast({ title: "Success", description: "Agent deleted" });
      fetchAgents();
    } catch (error) {
      toast({ title: "Error", description: "Failed to delete agent", variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Agents Configurator</h1>
      
      <Card>
        <CardHeader>
          <CardTitle>{form.id ? "Edit Agent" : "New Agent"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2">
            <Label>Name</Label>
            <Input value={form.name || ""} onChange={e => setForm({...form, name: e.target.value})} />
          </div>
          <div className="grid gap-2">
            <Label>Language</Label>
            <Input value={form.language || ""} onChange={e => setForm({...form, language: e.target.value})} placeholder="en, ta, ta,en" />
          </div>
          <div className="grid gap-2">
            <Label>Voice ID</Label>
            <Input value={form.voice_id || ""} onChange={e => setForm({...form, voice_id: e.target.value})} />
          </div>
          <div className="grid gap-2">
            <Label>System Prompt</Label>
            <Input value={form.system_prompt || ""} onChange={e => setForm({...form, system_prompt: e.target.value})} />
          </div>
          <Button onClick={handleSave}>Save Agent</Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {loading ? <p>Loading...</p> : agents.map(agent => (
          <Card key={agent.id}>
            <CardHeader>
              <CardTitle>{agent.name}</CardTitle>
            </CardHeader>
            <CardContent>
              <p>Language: {agent.language}</p>
              <p>Voice: {agent.voice_id}</p>
              <div className="flex gap-2 mt-4">
                <Button variant="outline" onClick={() => setForm(agent)}>Edit</Button>
                <Button variant="destructive" onClick={() => handleDelete(agent.id)}>Delete</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
