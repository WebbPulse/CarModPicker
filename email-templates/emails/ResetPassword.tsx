import {
  Body,
  Button,
  Container,
  Head,
  Heading,
  Hr,
  Html,
  Link,
  Preview,
  Section,
  Text,
} from "@react-email/components";
import * as React from "react";

interface ResetPasswordProps {
  resetPasswordLink?: string;
}

export const ResetPassword = ({
  resetPasswordLink = "{{RESET_PASSWORD_LINK}}",
}: ResetPasswordProps) => (
  <Html>
    <Head />
    <Preview>Reset your CarModPicker password</Preview>
    <Body style={main}>
      <Container style={container}>
        <Section style={logoSection}>
          <Text style={logoText}>🔧 CarModPicker</Text>
        </Section>

        <Heading style={heading}>Reset your password</Heading>

        <Text style={paragraph}>
          We received a request to reset the password for your CarModPicker
          account. Click the button below to choose a new password.
        </Text>

        <Section style={buttonSection}>
          <Button style={button} href={resetPasswordLink}>
            Reset Password
          </Button>
        </Section>

        <Text style={paragraph}>
          Or copy and paste this link into your browser:
        </Text>
        <Link href={resetPasswordLink} style={link}>
          {resetPasswordLink}
        </Link>

        <Hr style={hr} />

        <Text style={footer}>
          If you didn't request a password reset, you can safely ignore this
          email — your password will remain unchanged. This link will expire
          in 1 hour.
        </Text>

        <Text style={footer}>
          &copy; {new Date().getFullYear()} CarModPicker. All rights reserved.
        </Text>
      </Container>
    </Body>
  </Html>
);

export default ResetPassword;

const main: React.CSSProperties = {
  backgroundColor: "#f4f4f5",
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif',
};

const container: React.CSSProperties = {
  margin: "0 auto",
  padding: "20px 0 48px",
  maxWidth: "560px",
};

const logoSection: React.CSSProperties = {
  padding: "32px 40px 0",
};

const logoText: React.CSSProperties = {
  fontSize: "24px",
  fontWeight: "700",
  color: "#18181b",
  margin: "0",
};

const heading: React.CSSProperties = {
  fontSize: "28px",
  fontWeight: "700",
  color: "#18181b",
  padding: "16px 40px 0",
  margin: "0",
};

const paragraph: React.CSSProperties = {
  fontSize: "15px",
  lineHeight: "1.6",
  color: "#52525b",
  padding: "8px 40px 0",
  margin: "0",
};

const buttonSection: React.CSSProperties = {
  padding: "24px 40px",
};

const button: React.CSSProperties = {
  backgroundColor: "#dc2626",
  borderRadius: "8px",
  color: "#ffffff",
  fontSize: "15px",
  fontWeight: "600",
  textDecoration: "none",
  textAlign: "center" as const,
  display: "block",
  padding: "14px 24px",
};

const link: React.CSSProperties = {
  fontSize: "13px",
  color: "#dc2626",
  padding: "0 40px",
  wordBreak: "break-all",
};

const hr: React.CSSProperties = {
  borderColor: "#e4e4e7",
  margin: "32px 40px 24px",
};

const footer: React.CSSProperties = {
  fontSize: "13px",
  lineHeight: "1.5",
  color: "#a1a1aa",
  padding: "0 40px 8px",
  margin: "0",
};
