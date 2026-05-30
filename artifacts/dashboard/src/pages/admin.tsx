import { useState } from "react";
import { useAppStore } from "@/lib/store";
import { 
  useGetAdminStats, 
  useListAdminUsers, 
  useAdminCreateKey, 
  useAdminRevokeKey, 
  useGetAuditLog, 
  useGetAdminRequests 
} from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { 
  Users, Activity, Clock, Zap, Lock, ShieldAlert, 
  LogOut, Trash2, KeyRound, Terminal, AlertCircle
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

export default function Admin() {
  const { adminMasterKey, setAdminMasterKey, logoutAdmin } = useAppStore();
  const [loginKey, setLoginKey] = useState("");

  if (!adminMasterKey) {
    return (
      <div className="flex items-center justify-center min-h-[70vh]">
        <Card className="w-full max-w-md border-border bg-card shadow-2xl">
          <CardHeader className="text-center pb-8 border-b border-border/50">
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4 text-primary">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <CardTitle className="text-2xl font-mono">Restricted Access</CardTitle>
            <CardDescription>Enter the master key to access the administration panel.</CardDescription>
          </CardHeader>
          <CardContent className="pt-8">
            <form onSubmit={(e) => { e.preventDefault(); setAdminMasterKey(loginKey); }} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="masterKey">Master Key</Label>
                <Input
                  id="masterKey"
                  type="password"
                  value={loginKey}
                  onChange={(e) => setLoginKey(e.target.value)}
                  placeholder="••••••••••••••••"
                  className="font-mono bg-background"
                  autoFocus
                />
              </div>
              <Button type="submit" className="w-full h-12 text-base">
                <Lock className="w-4 h-4 mr-2" />
                Authenticate
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <AdminDashboard onLogout={logoutAdmin} />;
}

function AdminDashboard({ onLogout }: { onLogout: () => void }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  // Queries
  const { data: stats, isLoading: statsLoading } = useGetAdminStats({
    query: { refetchInterval: 30000 }
  });
  const { data: users, isLoading: usersLoading } = useListAdminUsers();
  const { data: auditLogs } = useGetAuditLog({ limit: 50 });
  const { data: requests } = useGetAdminRequests({ limit: 50 });

  // Mutations
  const createKeyMutation = useAdminCreateKey({
    mutation: {
      onSuccess: () => {
        toast({ title: "Key Created", description: "Successfully provisioned new API key." });
        queryClient.invalidateQueries({ queryKey: ["/api/admin/users"] });
        queryClient.invalidateQueries({ queryKey: ["/api/admin/stats"] });
        setIsCreateOpen(false);
      },
      onError: (err) => toast({ variant: "destructive", title: "Error", description: err.message })
    }
  });

  const revokeKeyMutation = useAdminRevokeKey({
    mutation: {
      onSuccess: () => {
        toast({ title: "Key Revoked", description: "The API key has been permanently deactivated." });
        queryClient.invalidateQueries({ queryKey: ["/api/admin/users"] });
      },
      onError: (err) => toast({ variant: "destructive", title: "Error", description: err.message })
    }
  });

  const handleCreateKey = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    createKeyMutation.mutate({
      data: {
        email: formData.get("email") as string,
        name: formData.get("name") as string,
        plan: formData.get("plan") as string,
        rate_limit: Number(formData.get("rateLimit")),
      }
    });
  };

  return (
    <div className="space-y-8 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-1">Administration</h1>
          <p className="text-muted-foreground">Platform overview and access control.</p>
        </div>
        <Button variant="outline" onClick={onLogout} className="text-muted-foreground hover:text-foreground">
          <LogOut className="w-4 h-4 mr-2" />
          Exit Admin
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-card border-border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
            <Users className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statsLoading ? "-" : stats?.total_users}</div>
            <p className="text-xs text-muted-foreground mt-1">Registered API keys</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Requests</CardTitle>
            <Activity className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statsLoading ? "-" : stats?.total_requests}</div>
            <p className="text-xs text-muted-foreground mt-1">
              <span className="text-primary font-medium">{stats?.requests_today || 0}</span> today
            </p>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Response Time</CardTitle>
            <Clock className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statsLoading ? "-" : `${stats?.avg_response_time}ms`}</div>
            <p className="text-xs text-muted-foreground mt-1">Across all models</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Users</CardTitle>
            <Zap className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{statsLoading ? "-" : stats?.active_users_today || 0}</div>
            <p className="text-xs text-muted-foreground mt-1">Unique keys used today</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="users" className="space-y-6">
        <TabsList className="bg-muted/50 border border-border">
          <TabsTrigger value="users">Users & Keys</TabsTrigger>
          <TabsTrigger value="requests">Request Logs</TabsTrigger>
          <TabsTrigger value="audit">Audit Log</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="space-y-4">
          <div className="flex justify-end">
            <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
              <DialogTrigger asChild>
                <Button>
                  <KeyRound className="w-4 h-4 mr-2" />
                  Provision Key
                </Button>
              </DialogTrigger>
              <DialogContent className="border-border bg-card">
                <DialogHeader>
                  <DialogTitle>Provision API Key</DialogTitle>
                  <DialogDescription>Create a new API key for a user with specific limits.</DialogDescription>
                </DialogHeader>
                <form onSubmit={handleCreateKey} className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Name</Label>
                    <Input id="name" name="name" required className="bg-background" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input id="email" name="email" type="email" required className="bg-background" />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="plan">Plan</Label>
                      <Select name="plan" defaultValue="free">
                        <SelectTrigger className="bg-background">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="free">Free</SelectItem>
                          <SelectItem value="pro">Pro</SelectItem>
                          <SelectItem value="enterprise">Enterprise</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="rateLimit">Daily Limit</Label>
                      <Input id="rateLimit" name="rateLimit" type="number" defaultValue="100" className="bg-background" />
                    </div>
                  </div>
                  <div className="pt-4 flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
                    <Button type="submit" disabled={createKeyMutation.isPending}>
                      {createKeyMutation.isPending ? "Creating..." : "Create Key"}
                    </Button>
                  </div>
                </form>
              </DialogContent>
            </Dialog>
          </div>

          <Card className="border-border bg-card overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead>User</TableHead>
                    <TableHead>API Key</TableHead>
                    <TableHead>Plan</TableHead>
                    <TableHead>Usage (Today)</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {usersLoading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">Loading users...</TableCell>
                    </TableRow>
                  ) : users?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">No users found</TableCell>
                    </TableRow>
                  ) : (
                    users?.map((user) => (
                      <TableRow key={user.id} className="border-border">
                        <TableCell>
                          <div className="font-medium">{user.name}</div>
                          <div className="text-xs text-muted-foreground">{user.email}</div>
                        </TableCell>
                        <TableCell>
                          <code className="px-2 py-1 bg-muted rounded text-xs font-mono text-primary/80">
                            {user.api_key.substring(0, 8)}...{user.api_key.substring(user.api_key.length - 4)}
                          </code>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className={
                            user.plan === 'enterprise' ? 'bg-primary/10 text-primary border-primary/20' : 
                            user.plan === 'pro' ? 'bg-blue-500/10 text-blue-500 border-blue-500/20' : ''
                          }>
                            {user.plan}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className="text-sm">{user.requests_used_today} / {user.rate_limit_per_day}</span>
                            <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                              <div 
                                className={`h-full ${user.requests_used_today >= user.rate_limit_per_day ? 'bg-destructive' : 'bg-primary'}`} 
                                style={{ width: `${Math.min(100, (user.requests_used_today / user.rate_limit_per_day) * 100)}%` }}
                              />
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(user.created_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button 
                            variant="ghost" 
                            size="icon"
                            className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            onClick={() => {
                              if (confirm('Are you sure you want to revoke this key?')) {
                                revokeKeyMutation.mutate({ keyId: user.api_key });
                              }
                            }}
                            disabled={revokeKeyMutation.isPending}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="requests" className="space-y-4">
          <Card className="border-border bg-card overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead>Time</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Request</TableHead>
                    <TableHead>Actions Taken</TableHead>
                    <TableHead>Latency</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {requests?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">No requests logged</TableCell>
                    </TableRow>
                  ) : (
                    requests?.map((req) => (
                      <TableRow key={req.id} className="border-border">
                        <TableCell className="text-xs whitespace-nowrap text-muted-foreground">
                          {new Date(req.timestamp).toLocaleString()}
                        </TableCell>
                        <TableCell className="text-sm">{req.user_email || 'Anonymous'}</TableCell>
                        <TableCell>
                          <div className="max-w-[200px] truncate text-sm" title={req.user_message}>
                            {req.user_message}
                          </div>
                        </TableCell>
                        <TableCell>
                          {req.actions_taken && req.actions_taken !== '[]' ? (
                            <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">
                              <Terminal className="w-3 h-3 mr-1" />
                              Executed
                            </Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm font-mono">{req.response_time_ms}ms</TableCell>
                        <TableCell>
                          {req.success ? (
                            <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/20">Success</Badge>
                          ) : (
                            <Badge variant="outline" className="bg-destructive/10 text-destructive border-destructive/20">Failed</Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="audit" className="space-y-4">
          <Card className="border-border bg-card overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead>Time</TableHead>
                    <TableHead>Event</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>IP Address</TableHead>
                    <TableHead>Details</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {auditLogs?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">No audit logs found</TableCell>
                    </TableRow>
                  ) : (
                    auditLogs?.map((log) => (
                      <TableRow key={log.id} className="border-border">
                        <TableCell className="text-xs whitespace-nowrap text-muted-foreground">
                          {new Date(log.timestamp).toLocaleString()}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-mono text-[10px] uppercase bg-muted/50">
                            {log.action}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">{log.user_email || 'System'}</TableCell>
                        <TableCell className="text-xs font-mono text-muted-foreground">{log.ip_address}</TableCell>
                        <TableCell className="text-sm max-w-[300px] truncate" title={log.details}>
                          {log.details}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
