"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import api from "@/lib/api";

type Doc = {
  id: string;
  url?: string;
  status: string;
};

export default function KnowledgePage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [url, setUrl] = useState("");
  const { toast } = useToast();

  const fetchDocs = async () => {
    try {
      const res = await api.get("/knowledge/docs");
      setDocs(res.data);
    } catch (error) {
      toast({ title: "Error", description: "Failed to fetch docs", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleAddUrl = async () => {
    try {
      await api.post("/knowledge/ingest/url", { url, agent_config_id: null });
      toast({ title: "Success", description: "URL added for processing" });
      setUrl("");
      fetchDocs();
    } catch (error) {
      toast({ title: "Error", description: "Failed to add URL", variant: "destructive" });
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/knowledge/docs/${id}`);
      toast({ title: "Success", description: "Doc deleted" });
      fetchDocs();
    } catch (error) {
      toast({ title: "Error", description: "Failed to delete doc", variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Knowledge Base</h1>
      
      <Card>
        <CardHeader>
          <CardTitle>Ingest URL</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://example.com" />
            <Button onClick={handleAddUrl}>Add URL</Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4">
        {loading ? <p>Loading...</p> : docs.map(doc => (
          <Card key={doc.id}>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <p className="font-semibold">{doc.url || doc.id}</p>
                <p className="text-sm text-gray-500">Status: {doc.status}</p>
              </div>
              <Button variant="destructive" onClick={() => handleDelete(doc.id)}>Delete</Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
