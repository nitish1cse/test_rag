"use client";

import React, { useState, useEffect } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Mail } from "lucide-react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { SetuLogo } from "../../components/ui/setu-logo";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Check for URL parameters and attempt login if they exist
    const email = searchParams.get('email');
    const password = searchParams.get('password');
    if (email && password) {
      handleLogin(email, password);
    }
  }, [searchParams]);

  const handleLogin = async (email: string, password: string) => {
    setError(null);
    setLoading(true);

    try {
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
        callbackUrl: "/dashboard"
      });

      console.log("SignIn result:", result);

      if (!result) {
        throw new Error("SignIn result is undefined");
      }

      if (result.error) {
        setError("Invalid email or password");
        console.error("SignIn error:", result.error);
      } else {
        console.log("Login successful, redirecting...");
        router.push(result.url || "/dashboard");
      }
    } catch (error) {
      console.error("Login error:", error);
      setError("An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const email = formData.get("email") as string;
    const password = formData.get("password") as string;
    await handleLogin(email, password);
  };

  return (
    <div className="container relative h-screen flex items-center justify-center">      
      <div className="mx-auto w-full max-w-[350px]">
        <div className="flex w-full flex-col items-center justify-center space-y-6">
          <div className="flex items-center justify-center w-[50px] h-[50px] rounded-full overflow-hidden bg-white shadow-sm mb-4">
            <SetuLogo size={50} className="object-contain" />
          </div>
          <div className="flex flex-col space-y-2 text-center w-full">
            <h1 className="text-2xl font-semibold tracking-tight">
              Welcome back
            </h1>
            <p className="text-sm text-muted-foreground">
              Enter your email to sign in to your account
            </p>
          </div>
          <div className={`grid gap-6 w-full`}>
            <form onSubmit={handleSubmit} className="w-full">
              <div className="grid gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="email" className="text-center">Email</Label>
                  <Input
                    id="email"
                    name="email"
                    placeholder="name@example.com"
                    type="email"
                    autoCapitalize="none"
                    autoComplete="email"
                    autoCorrect="off"
                    defaultValue={searchParams.get('email') || "admin@example.com"}
                    disabled={loading}
                    className="w-full"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="password" className="text-center">Password</Label>
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    defaultValue={searchParams.get('password') || "admin123"}
                    disabled={loading}
                    className="w-full"
                  />
                </div>
                {error && (
                  <div className="text-sm text-destructive bg-destructive/10 p-2 rounded-md text-center">
                    {error}
                  </div>
                )}
                <Button 
                  disabled={loading}
                  className="bg-[#5e65de] hover:bg-[#4a51c4] w-full"
                >
                  {loading ? "Signing in..." : "Sign in with Email"}
                </Button>
              </div>
            </form>
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">
                  Or continue with
                </span>
              </div>
            </div>
            <Button variant="outline" type="button" disabled={loading} className="w-full">
              <Mail className="mr-2 h-4 w-4" />
              Continue with Email
            </Button>
          </div>
          <p className="px-8 text-center text-sm text-muted-foreground">
            By clicking continue, you agree to our{" "}
            <a href="#" className="underline underline-offset-4 hover:text-[#5e65de]">
              Terms of Service
            </a>{" "}
            and{" "}
            <a href="#" className="underline underline-offset-4 hover:text-[#5e65de]">
              Privacy Policy
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
} 