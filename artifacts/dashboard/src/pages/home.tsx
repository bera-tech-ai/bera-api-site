import { useState } from "react";
import { useRegister } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { useAppStore } from "@/lib/store";
import { useLocation } from "wouter";
import {
  Terminal, Zap, Key, FolderOpen, GitBranch,
  Shield, Code2, CheckCircle2, Copy, ChevronRight,
  Activity, Users, Lock, MessageSquare
} from "lucide-react";

const DOMAIN = typeof window !== "undefined"
  ? window.location.origin
  : "";

const ENDPOINTS = [
  { method: "GET", path: "/api/ai/chat", desc: "AI chat — answer any question", params: "q, apikey", tag: "AI", tagColor: "text-green-400 border-green-500/20 bg-green-500/10" },
  { method: "GET", path: "/api/ai/agent", desc: "Agent mode — executes real actions (bash, files, GitHub)", params: "q, apikey", tag: "Agent", tagColor: "text-cyan-400 border-cyan-500/20 bg-cyan-500/10" },
  { method: "GET", path: "/api/ai/gemini", desc: "Gifted-compatible Gemini endpoint for existing bots", params: "q, apikey", tag: "AI", tagColor: "text-green-400 border-green-500/20 bg-green-500/10" },
  { method: "GET", path: "/api/ai/gpt", desc: "GPT-style endpoint — same AI, different path", params: "q, apikey", tag: "AI", tagColor: "text-green-400 border-green-500/20 bg-green-500/10" },
  { method: "POST", path: "/api/chat", desc: "Full-featured chat — AI + SSH + agent in one call", params: "apikey, message, ssh?, agent_mode?", tag: "Chat", tagColor: "text-blue-400 border-blue-500/20 bg-blue-500/10" },
  { method: "POST", path: "/api/agent", desc: "Execute bash, create files/folders, GitHub ops", params: "apikey, task", tag: "Agent", tagColor: "text-cyan-400 border-cyan-500/20 bg-cyan-500/10" },
  { method: "POST", path: "/api/github/push", desc: "Create a GitHub repo and push local files", params: "apikey, repo_name, description?", tag: "GitHub", tagColor: "text-purple-400 border-purple-500/20 bg-purple-500/10" },
  { method: "POST", path: "/api/register", desc: "Get a free API key instantly", params: "name, email, plan?", tag: "Keys", tagColor: "text-yellow-400 border-yellow-500/20 bg-yellow-500/10" },
  { method: "GET", path: "/api/verify-key", desc: "Verify key validity and check usage", params: "apikey", tag: "Keys", tagColor: "text-yellow-400 border-yellow-500/20 bg-yellow-500/10" },
];

const AGENT_CMDS = [
  "create folder myproject/src",
  "run: npm install express",
  "create github repo my-new-api",
  "list my github repos",
  "write file index.js with content console.log('hi')",
  "run: git status",
  "list files in myproject",
  "run: python3 --version",
];

function CopyBtn({ text }: { text: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setOk(true); setTimeout(() => setOk(false), 2000); }}
      className="absolute top-3 right-3 p-1.5 rounded text-muted-foreground hover:text-foreground"
    >
      {ok ? <CheckCircle2 className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
    </button>
  );
}

function CodeBlock({ code, lang = "bash" }: { code: string; lang?: string }) {
  return (
    <div className="relative rounded-lg border border-border bg-black overflow-hidden">
      <div className="flex items-center gap-1.5 px-4 py-2 border-b border-border/40 bg-muted/10">
        <span className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
        <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/60" />
        <span className="w-2.5 h-2.5 rounded-full bg-green-500/60" />
        <span className="ml-2 text-xs text-muted-foreground font-mono">{lang}</span>
      </div>
      <CopyBtn text={code} />
      <pre className="p-4 text-sm font-mono text-gray-300 overflow-x-auto leading-relaxed whitespace-pre-wrap">{code}</pre>
    </div>
  );
}

export default function Home() {
  const { toast } = useToast();
  const [, setLocation] = useLocation();
  const setApiKey = useAppStore(s => s.setApiKey);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "" });
  const [newKey, setNewKey] = useState("");

  const registerMutation = useRegister({
    mutation: {
      onSuccess: (data) => {
        setNewKey(data.api_key);
        setApiKey(data.api_key);
        toast({ title: "API Key Created" });
      },
      onError: (e) => toast({ variant: "destructive", title: "Error", description: e.message }),
    },
  });

  return (
    <div className="space-y-24 pb-24">

      {/* ── Hero ── */}
      <section className="text-center pt-16 pb-4">
        <Badge variant="outline" className="mb-6 px-4 py-1.5 border-primary/30 text-primary bg-primary/5 font-mono text-xs">
          <Activity className="w-3 h-3 mr-2 inline" /> v2.0 — Agent Mode Live
        </Badge>
        <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-6 leading-none">
          <span className="block text-foreground">Bera AI</span>
          <span className="block bg-gradient-to-r from-primary to-blue-500 bg-clip-text text-transparent">Developer API</span>
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed">
          An AI API that doesn't just answer questions — it{" "}
          <span className="text-foreground font-medium">executes real actions</span>.
          Create files, run bash commands, manage GitHub, all through natural language.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4">
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="lg" className="h-12 px-8 text-base font-semibold">
                <Key className="w-5 h-5 mr-2" /> Get Free API Key
              </Button>
            </DialogTrigger>
            <DialogContent className="border-border bg-card">
              <DialogHeader>
                <DialogTitle>Get Your Free API Key</DialogTitle>
                <DialogDescription>100 requests/day on the free plan. No credit card.</DialogDescription>
              </DialogHeader>
              {newKey ? (
                <div className="space-y-4 py-2">
                  <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20">
                    <p className="text-sm text-green-400 font-semibold mb-2 flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4" /> Key created — save it now
                    </p>
                    <code className="block font-mono text-xs bg-black rounded p-3 text-primary break-all">{newKey}</code>
                  </div>
                  <Button className="w-full" onClick={() => { setOpen(false); setLocation("/dashboard"); }}>
                    Open Console <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              ) : (
                <form className="space-y-4 py-2"
                  onSubmit={e => { e.preventDefault(); registerMutation.mutate({ data: form }); }}>
                  <div className="space-y-2">
                    <Label>Name</Label>
                    <Input placeholder="Bruce Bera" value={form.name}
                      onChange={e => setForm({ ...form, name: e.target.value })} required className="bg-background" />
                  </div>
                  <div className="space-y-2">
                    <Label>Email</Label>
                    <Input type="email" placeholder="you@example.com" value={form.email}
                      onChange={e => setForm({ ...form, email: e.target.value })} required className="bg-background" />
                  </div>
                  <Button type="submit" className="w-full h-11" disabled={registerMutation.isPending}>
                    {registerMutation.isPending ? "Creating..." : "Create Free Key"}
                  </Button>
                </form>
              )}
            </DialogContent>
          </Dialog>
          <Button variant="outline" size="lg" className="h-12 px-8 text-base" onClick={() => setLocation("/dashboard")}>
            Try Console <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-8 mt-12 text-sm text-muted-foreground">
          {[["Zap", "Agent Actions"], ["GitBranch", "GitHub Integration"], ["Shield", "API Key Auth"], ["Users", "Free Tier"]].map(([, label]) => (
            <span key={label} className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />{label}
            </span>
          ))}
        </div>
      </section>

      {/* ── Quick Start ── */}
      <section className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-2">Quick Start</h2>
          <p className="text-muted-foreground">Integrate in under 60 seconds</p>
        </div>
        <Tabs defaultValue="chat">
          <TabsList className="bg-muted/40 border border-border mb-4">
            <TabsTrigger value="chat">AI Chat</TabsTrigger>
            <TabsTrigger value="agent">Agent</TabsTrigger>
            <TabsTrigger value="bot">Bot Integration</TabsTrigger>
            <TabsTrigger value="register">Register</TabsTrigger>
          </TabsList>
          <TabsContent value="chat">
            <CodeBlock lang="bash" code={`# Ask any question
curl "${DOMAIN}/api/ai/chat?q=What+is+Node.js&apikey=YOUR_KEY"

# Response
{ "status": true, "result": "Node.js is a JavaScript runtime...", "creator": "Bruce Bera" }`} />
          </TabsContent>
          <TabsContent value="agent">
            <CodeBlock lang="bash" code={`# Create a folder
curl "${DOMAIN}/api/ai/agent?q=create+folder+myproject/src&apikey=YOUR_KEY"

# Run a bash command
curl "${DOMAIN}/api/ai/agent?q=run:+npm+install+express&apikey=YOUR_KEY"

# Create a GitHub repo
curl "${DOMAIN}/api/ai/agent?q=create+github+repo+my-api&apikey=YOUR_KEY"

# List GitHub repos
curl "${DOMAIN}/api/ai/agent?q=list+my+github+repos&apikey=YOUR_KEY"`} />
          </TabsContent>
          <TabsContent value="bot">
            <CodeBlock lang="javascript" code={`// In your cloud-bera Config/index.js
module.exports = {
  // Point your bot to the Bera AI API
  nickApiEndpoint: '${DOMAIN}/api/ai/chat',
  nickApiKey: 'YOUR_BERA_API_KEY',
  // ...
}

// The bot will now use:
// GET ${DOMAIN}/api/ai/chat?q=<message>&apikey=<key>
// GET ${DOMAIN}/api/ai/gemini?q=<message>&apikey=<key>  // fallback
// GET ${DOMAIN}/api/ai/gpt?q=<message>&apikey=<key>     // fallback`} />
          </TabsContent>
          <TabsContent value="register">
            <CodeBlock lang="bash" code={`curl -X POST "${DOMAIN}/api/register" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"Bruce Bera","email":"you@example.com"}'

# Response
{ "status": true, "api_key": "bruce_live_xxxx...", "plan": "free", "daily_limit": 100 }`} />
          </TabsContent>
        </Tabs>
      </section>

      {/* ── Agent capabilities ── */}
      <section className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-2">Agent Mode</h2>
          <p className="text-muted-foreground max-w-xl mx-auto">
            Unlike ordinary AI APIs, Bera Agent executes real operations on the server — no SSH needed.
          </p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            { icon: FolderOpen, title: "Files & Folders", desc: "Create, read, delete dirs and files in natural language" },
            { icon: Terminal, title: "Bash Commands", desc: "Run any shell command — npm, git, python, node" },
            { icon: GitBranch, title: "GitHub", desc: "Create repos, list repos, push code — all from the API" },
            { icon: MessageSquare, title: "AI Brain", desc: "Powered by Groq + Gemini with multi-provider fallback" },
          ].map(({ icon: Icon, title, desc }) => (
            <Card key={title} className="bg-card border-border hover:border-primary/30 transition-colors">
              <CardHeader className="pb-2">
                <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center mb-3">
                  <Icon className="w-5 h-5 text-primary" />
                </div>
                <CardTitle className="text-sm">{title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">{desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="p-5 rounded-xl bg-muted/20 border border-border">
          <p className="text-xs font-semibold mb-3 text-muted-foreground uppercase tracking-wider">Natural language commands</p>
          <div className="grid md:grid-cols-2 gap-2">
            {AGENT_CMDS.map(cmd => (
              <div key={cmd} className="flex items-center gap-2 p-2.5 rounded-lg bg-background border border-border font-mono text-xs">
                <span className="text-primary shrink-0">❯</span>
                <span>{cmd}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── API Reference ── */}
      <section className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-2">API Reference</h2>
          <p className="text-muted-foreground text-sm">
            Base URL: <code className="bg-muted px-2 py-0.5 rounded font-mono">{DOMAIN}</code>
            {" · "}
            <a href="/api/docs" target="_blank" className="text-primary hover:underline">Swagger Docs</a>
          </p>
        </div>
        <div className="space-y-2">
          {ENDPOINTS.map(ep => (
            <div key={ep.path + ep.method}
              className="flex flex-col sm:flex-row sm:items-center gap-3 p-4 rounded-xl bg-card border border-border hover:border-primary/20 transition-colors">
              <div className="flex items-center gap-3 sm:w-72 shrink-0">
                <Badge variant="outline"
                  className={`font-mono text-xs font-bold shrink-0 ${ep.method === "GET" ? "bg-green-500/10 text-green-400 border-green-500/20" : "bg-blue-500/10 text-blue-400 border-blue-500/20"}`}>
                  {ep.method}
                </Badge>
                <code className="text-xs font-mono text-primary">{ep.path}</code>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm">{ep.desc}</p>
                <p className="text-xs text-muted-foreground mt-0.5 font-mono truncate">params: {ep.params}</p>
              </div>
              <Badge variant="outline" className={`text-xs shrink-0 ${ep.tagColor}`}>{ep.tag}</Badge>
            </div>
          ))}
        </div>
        <div className="mt-5 flex justify-center">
          <Button variant="outline" size="sm" asChild>
            <a href="/api/docs" target="_blank" rel="noopener noreferrer">
              <Code2 className="w-4 h-4 mr-2" /> Full Swagger Docs
            </a>
          </Button>
        </div>
      </section>

      {/* ── Plans ── */}
      <section className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-2">Plans</h2>
          <p className="text-muted-foreground">Start free, scale as you grow</p>
        </div>
        <div className="grid md:grid-cols-3 gap-5">
          {[
            { name: "Free", price: "$0", limit: "100 req/day", features: ["AI Chat", "Agent Mode", "File & Bash Ops", "Community Support"] },
            { name: "Pro", price: "Contact", limit: "10,000 req/day", features: ["Everything Free", "GitHub Integration", "Priority AI", "SSH Access"], highlight: true },
            { name: "Enterprise", price: "Contact", limit: "Unlimited", features: ["Everything Pro", "Custom Limits", "Dedicated Support", "SLA Guarantee"] },
          ].map(plan => (
            <Card key={plan.name} className={`border-border ${plan.highlight ? "border-primary/40 bg-primary/5" : "bg-card"}`}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{plan.name}</CardTitle>
                  {plan.highlight && <Badge className="text-xs">Popular</Badge>}
                </div>
                <div>
                  <span className="text-2xl font-bold">{plan.price}</span>
                  <p className="text-xs text-muted-foreground mt-1">{plan.limit}</p>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {plan.features.map(f => (
                  <div key={f} className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="w-3.5 h-3.5 text-primary shrink-0" />{f}
                  </div>
                ))}
                <Button variant={plan.highlight ? "default" : "outline"} size="sm" className="w-full mt-3"
                  onClick={() => setOpen(true)}>
                  {plan.name === "Free" ? "Get Started" : "Contact Us"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* ── Bot integration callout ── */}
      <section className="max-w-3xl mx-auto">
        <div className="rounded-2xl bg-gradient-to-br from-primary/10 to-blue-500/10 border border-primary/20 p-8 text-center">
          <Lock className="w-10 h-10 text-primary mx-auto mb-4" />
          <h3 className="text-2xl font-bold mb-3">Connecting cloud-bera?</h3>
          <p className="text-muted-foreground mb-6 text-sm">
            Set <code className="bg-black/40 px-2 py-0.5 rounded font-mono text-xs">NICK_API</code> in your bot's{" "}
            <code className="bg-black/40 px-2 py-0.5 rounded font-mono text-xs">Config/index.js</code> to point here.
          </p>
          <CodeBlock lang="javascript" code={`// Config/index.js
nickApiEndpoint: '${DOMAIN}/api/ai/chat',
nickApiKey: 'YOUR_BERA_API_KEY',`} />
          <p className="text-xs text-muted-foreground mt-4">
            Built by{" "}
            <a href="https://github.com/bera-tech-ai" target="_blank" rel="noopener noreferrer"
              className="text-primary hover:underline">Bera Tech</a>
          </p>
        </div>
      </section>

    </div>
  );
}
