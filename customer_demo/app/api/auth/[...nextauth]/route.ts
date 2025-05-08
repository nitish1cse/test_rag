import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";
import { JWT } from "next-auth/jwt";
import { Session } from "next-auth";

interface CustomSession extends Session {
  user: {
    id?: string;
    email?: string | null;
    name?: string | null;
  };
}

const handler = NextAuth({
  debug: true, // Enable debug mode
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials, req) {
        try {
          console.log("Authorizing with credentials:", { email: credentials?.email }); // Don't log passwords

          // This is a demo app, so we'll use hardcoded credentials
          // In production, you should use a proper database
          const validCredentials = {
            email: "admin@example.com",
            // Password: "admin123"
            passwordHash: "$2a$10$IeULI9HA3PW5icZR/W6reuWz1ZeuT3WDr01Y/yZ4NcfquPH3iYgqa"
          };

          if (!credentials?.email || !credentials?.password) {
            console.log("Missing credentials");
            throw new Error("Missing credentials");
          }

          const isValidEmail = credentials.email === validCredentials.email;
          const isValidPassword = await bcrypt.compare(
            credentials.password,
            validCredentials.passwordHash
          );

          console.log("Validation result:", { 
            isValidEmail,
            isValidPassword,
            providedEmail: credentials.email,
            expectedEmail: validCredentials.email
          });

          if (isValidEmail && isValidPassword) {
            console.log("Login successful");
            return {
              id: "1",
              email: credentials.email,
              name: "Admin User",
            };
          }

          throw new Error("Invalid credentials");
        } catch (error) {
          console.error("Authorization error:", error);
          throw error;
        }
      }
    })
  ],
  pages: {
    signIn: "/login",
    error: "/login",
  },
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.email = user.email;
        token.name = user.name;
      }
      return token;
    },
    async session({ session, token }): Promise<CustomSession> {
      return {
        ...session,
        user: {
          ...session.user,
          email: token.email,
          name: token.name,
        },
      };
    }
  }
});

export { handler as GET, handler as POST }; 