import { useState, useRef, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { useChat, useVerifyKey, getVerifyKeyQueryKey, ChatResult } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, Server, Key, TerminalSquare, Settings2, Clock, CheckCircle2, XCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  result?: ChatResult;
  timestamp: Date;
}

export default function Dashboard() {
  const { apiKey, setApiKey, sshConfig, setSshConfig } = useAppStore();
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  const [localApiKey, setLocalApiKey] = useState(apiKey);
  const [localSsh, setLocalSsh] = useState(sshConfig);

  const { data: keyStatus, isLoading: keyVerifying } = useVerifyKey(
    { apikey: localApiKey },
    { query: { enabled: !!localApiKey, retry: false } }
  );

  const chatMutation = useChat({
    mutation: {
      onSuccess: (data) => {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.result,
            result: data,
            timestamp: new Date()
          }
        ]);
      },
      onError: (error) => {
        toast({
          variant: "destructive",
          title: "Chat Request Failed",
          description: error.message || "An error occurred while communicating with the API.",
        });
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Error: Could not complete the request. Please check your API key and connection.",
            timestamp: new Date()
          }
        ]);
      }
    }
  });

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, chatMutation.isPending]);

  const handleSaveSettings = () => {
    setApiKey(localApiKey);
    setSshConfig({
      host: localSsh.host || undefined,
      port: localSsh.port ? Number(localSsh.port) : undefined,
      username: localSsh.username || undefined,
      password: localSsh.password || undefined,
      private_key: localSsh.private_key || undefined,
    });
    toast({
      title: "Settings Saved",
      description: "API Key and SSH configuration updated.",
    });
  };

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || !apiKey) {
      if (!apiKey) {
        toast({
          variant: "destructive",
          title: "API Key Required",
          description: "Please configure your API key in the settings panel first.",
        });
      }
      return;
    }

    const payload = {
      apikey: apiKey,
      message: message,
      ssh: Object.keys(sshConfig).length > 0 ? sshConfig : undefined,
    };

    setMessages((prev) => [
      ...prev,
      { role: "user", content: message, timestamp: new Date() }
    ]);
    
    setMessage("");
    chatMutation.mutate({ data: payload });
  };

  return (
    <div className="grid lg:grid-cols-4 gap-6 h-[calc(100vh-8rem)]">
      {/* Sidebar / Settings */}
      <div className="lg:col-span-1 flex flex-col gap-6">
        <Card className="bg-card border-border">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg flex items-center gap-2">
              <Key className="w-5 h-5 text-primary" />
              API Authentication
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>API Key</Label>
              <Input 
                type="password"
                placeholder="sk_..."
                value={localApiKey}
                onChange={(e) => setLocalApiKey(e.target.value)}
                className="font-mono text-sm"
              />
            </div>
            {localApiKey && (
              <div className="p-3 bg-muted rounded-md text-sm">
                {keyVerifying ? (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Skeleton className="w-4 h-4 rounded-full" />
                    Verifying...
                  </div>
                ) : keyStatus?.valid ? (
                  <div className="flex items-center gap-2 text-green-500">
                    <CheckCircle2 className="w-4 h-4" />
                    Valid Key ({keyStatus.plan} Plan)
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-destructive">
                    <XCircle className="w-4 h-4" />
                    Invalid or Expired Key
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-card border-border flex-1">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg flex items-center gap-2">
              <Server className="w-5 h-5 text-primary" />
              SSH Target (Optional)
            </CardTitle>
            <CardDescription>
              Provide credentials to allow the AI to run commands directly on your server.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2 space-y-2">
                <Label>Host</Label>
                <Input 
                  placeholder="192.168.1.10"
                  value={localSsh.host || ""}
                  onChange={(e) => setLocalSsh({...localSsh, host: e.target.value})}
                  className="font-mono text-sm"
                />
              </div>
              <div className="space-y-2">
                <Label>Port</Label>
                <Input 
                  type="number"
                  placeholder="22"
                  value={localSsh.port || ""}
                  onChange={(e) => setLocalSsh({...localSsh, port: Number(e.target.value)})}
                  className="font-mono text-sm"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Username</Label>
              <Input 
                placeholder="root"
                value={localSsh.username || ""}
                onChange={(e) => setLocalSsh({...localSsh, username: e.target.value})}
                className="font-mono text-sm"
              />
            </div>
            <div className="space-y-2">
              <Label>Password</Label>
              <Input 
                type="password"
                placeholder="••••••••"
                value={localSsh.password || ""}
                onChange={(e) => setLocalSsh({...localSsh, password: e.target.value})}
                className="font-mono text-sm"
              />
            </div>
            <div className="space-y-2">
              <Label>Private Key</Label>
              <Textarea 
                placeholder="-----BEGIN RSA PRIVATE KEY-----"
                value={localSsh.private_key || ""}
                onChange={(e) => setLocalSsh({...localSsh, private_key: e.target.value})}
                className="font-mono text-xs min-h-[100px]"
              />
            </div>
            <Button onClick={handleSaveSettings} className="w-full">
              <Settings2 className="w-4 h-4 mr-2" />
              Save Configuration
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Main Chat Area */}
      <Card className="lg:col-span-3 flex flex-col bg-card border-border overflow-hidden">
        <CardHeader className="border-b border-border bg-muted/20 py-3">
          <CardTitle className="text-base flex items-center gap-2">
            <TerminalSquare className="w-5 h-5 text-primary" />
            API Console
          </CardTitle>
        </CardHeader>
        
        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
          <div className="space-y-6">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground py-20">
                <TerminalSquare className="w-12 h-12 mb-4 opacity-20" />
                <p className="text-lg font-medium mb-2">No active session</p>
                <p className="text-sm max-w-sm">
                  Enter a message below to start interacting with the Bruce Bera AI. Ensure your API key is configured.
                </p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] rounded-lg p-4 ${
                    msg.role === 'user' 
                      ? 'bg-primary text-primary-foreground ml-auto' 
                      : 'bg-muted text-foreground border border-border'
                  }`}>
                    <div className="flex items-center justify-between mb-2 gap-4">
                      <span className="font-semibold text-xs opacity-75">
                        {msg.role === 'user' ? 'You' : 'Bruce Bera AI'}
                      </span>
                      <span className="text-[10px] opacity-50 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {msg.timestamp.toLocaleTimeString()}
                      </span>
                    </div>
                    
                    {msg.role === 'user' ? (
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    ) : (
                      <Tabs defaultValue="formatted" className="w-full">
                        <TabsList className="h-8 mb-4 bg-background/50">
                          <TabsTrigger value="formatted" className="text-xs px-3 py-1">Formatted</TabsTrigger>
                          <TabsTrigger value="raw" className="text-xs px-3 py-1">Raw JSON</TabsTrigger>
                        </TabsList>
                        
                        <TabsContent value="formatted" className="mt-0 space-y-4">
                          <div className="prose prose-sm dark:prose-invert max-w-none">
                            <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                          </div>
                          
                          {msg.result?.actions_taken && msg.result.actions_taken.length > 0 && (
                            <div className="mt-4 pt-4 border-t border-border/50">
                              <h4 className="text-xs font-semibold mb-2 uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                                <TerminalSquare className="w-3 h-3" /> Actions Taken
                              </h4>
                              <ul className="space-y-1">
                                {msg.result.actions_taken.map((action, i) => (
                                  <li key={i} className="text-xs font-mono bg-background/50 px-2 py-1 rounded border border-border/50 flex items-start gap-2">
                                    <span className="text-primary mt-0.5">❯</span>
                                    <span>{action}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </TabsContent>
                        
                        <TabsContent value="raw" className="mt-0">
                          <pre className="p-4 rounded bg-black text-gray-300 font-mono text-xs overflow-x-auto border border-border/50">
                            {JSON.stringify(msg.result, null, 2)}
                          </pre>
                        </TabsContent>
                      </Tabs>
                    )}
                  </div>
                </div>
              ))
            )}
            
            {chatMutation.isPending && (
              <div className="flex justify-start">
                <div className="max-w-[85%] rounded-lg p-4 bg-muted border border-border min-w-[200px]">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-primary/50 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                      <div className="w-2 h-2 bg-primary/50 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                      <div className="w-2 h-2 bg-primary/50 rounded-full animate-bounce"></div>
                    </div>
                    Processing request...
                  </div>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        <div className="p-4 border-t border-border bg-card">
          <form onSubmit={handleSendMessage} className="flex gap-4">
            <Input
              placeholder="Ask a question or request a command..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="flex-1 bg-background"
              disabled={chatMutation.isPending}
            />
            <Button type="submit" disabled={chatMutation.isPending || !message.trim()}>
              <Send className="w-4 h-4 mr-2" />
              Send
            </Button>
          </form>
        </div>
      </Card>
    </div>
  );
}
