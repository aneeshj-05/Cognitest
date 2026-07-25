import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { validateInvitation, acceptInvitation, type ValidationResponse } from "@/services/backendClient"
import { useAuth } from "@/context/AuthContext"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Loader2, Mail, CheckCircle2, XCircle } from "lucide-react"

export default function InviteLandingPage() {
    const [searchParams] = useSearchParams()
    const token = searchParams.get("token")
    const navigate = useNavigate()
    const { user } = useAuth()
    
    const [validation, setValidation] = useState<ValidationResponse | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState("")
    const [accepting, setAccepting] = useState(false)
    
    useEffect(() => {
        if (!token) {
            setError("No invitation token provided.")
            setLoading(false)
            return
        }
        
        validateInvitation(token)
            .then(res => {
                setValidation(res)
                setLoading(false)
            })
            .catch(err => {
                setError(err.message || "Failed to validate invitation.")
                setLoading(false)
            })
    }, [token])
    
    const handleAccept = async () => {
        if (!token) return
        setAccepting(true)
        setError("")
        try {
            await acceptInvitation(token)
            // Redirect to dashboard after accepting
            navigate("/dashboard")
        } catch (err: any) {
            setError(err.message || "Failed to accept invitation.")
            setAccepting(false)
        }
    }
    
    if (loading) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-muted/30">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        )
    }
    
    return (
        <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
            <Card className="w-full max-w-md shadow-lg border-border/50">
                <CardHeader className="space-y-1 pb-4 text-center">
                    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                        {validation?.valid ? (
                            <Mail className="h-6 w-6 text-primary" />
                        ) : (
                            <XCircle className="h-6 w-6 text-destructive" />
                        )}
                    </div>
                    <CardTitle className="text-2xl font-bold tracking-tight">
                        {validation?.valid ? "You've been invited!" : "Invalid Invitation"}
                    </CardTitle>
                    <CardDescription className="text-sm">
                        {error || (validation && !validation.valid && validation.message) || 
                            "Join your team to start collaborating."}
                    </CardDescription>
                </CardHeader>
                
                {validation?.valid && validation.invitation && (
                    <CardContent className="space-y-4 pt-4">
                        <div className="rounded-lg border border-border bg-muted/50 p-4 space-y-3">
                            <div className="grid grid-cols-[1fr_2fr] gap-2 text-sm">
                                <span className="font-semibold text-muted-foreground">Email:</span>
                                <span className="truncate">{validation.invitation.email}</span>
                                
                                {validation.invitation.workspace && (
                                    <>
                                        <span className="font-semibold text-muted-foreground">Workspace:</span>
                                        <span className="truncate">{validation.invitation.workspace.name}</span>
                                    </>
                                )}
                                
                                {validation.invitation.project && (
                                    <>
                                        <span className="font-semibold text-muted-foreground">Project:</span>
                                        <span className="truncate">{validation.invitation.project.name}</span>
                                    </>
                                )}
                                
                                <span className="font-semibold text-muted-foreground">Role:</span>
                                <span className="truncate">{validation.invitation.role.name}</span>
                                
                                {validation.invitation.inviter && (
                                    <>
                                        <span className="font-semibold text-muted-foreground">Invited By:</span>
                                        <span className="truncate">{validation.invitation.inviter.name}</span>
                                    </>
                                )}
                            </div>
                        </div>
                        
                        {error && (
                            <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive">
                                {error}
                            </div>
                        )}
                    </CardContent>
                )}
                
                <CardFooter className="flex flex-col gap-3 pb-6">
                    {validation?.valid ? (
                        user ? (
                            user.email === validation.invitation?.email ? (
                                <Button 
                                    className="w-full" 
                                    onClick={handleAccept} 
                                    disabled={accepting}
                                >
                                    {accepting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                                    Accept Invitation
                                </Button>
                            ) : (
                                <div className="text-center text-sm text-destructive w-full rounded-md bg-destructive/10 p-3">
                                    You are logged in as {user.email}. This invitation is for {validation.invitation?.email}. 
                                    Please log out and log in with the correct account.
                                </div>
                            )
                        ) : (
                            <div className="flex w-full flex-col gap-2">
                                <Button 
                                    className="w-full" 
                                    onClick={() => navigate(`/signup?inviteToken=${token}`)}
                                >
                                    Create Account
                                </Button>
                                <Button 
                                    variant="outline"
                                    className="w-full" 
                                    onClick={() => navigate(`/login?inviteToken=${token}`)}
                                >
                                    Log In
                                </Button>
                            </div>
                        )
                    ) : (
                        <Button 
                            className="w-full" 
                            variant="secondary"
                            onClick={() => navigate("/")}
                        >
                            Return to Home
                        </Button>
                    )}
                </CardFooter>
            </Card>
        </div>
    )
}
