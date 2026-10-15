
import React from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  Pressable,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { isScanResult, type ScanResult } from "../utils/scan-result";

function getDisplayStatus(status: ScanResult["status"] | undefined): ScanResult["status"] {
  return status === "VERIFIED" ? "UNVERIFIED" : status ?? "UNVERIFIED";
}

export default function ResultScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ result?: string | string[] }>();
  const resultParam = Array.isArray(params.result)
    ? params.result[0]
    : params.result;

  let result: ScanResult | null = null;

  try {
    if (typeof resultParam === "string") {
      const parsed: unknown = JSON.parse(resultParam);
      if (isScanResult(parsed)) result = parsed;
    }
  } catch {
    result = null;
  }

  // Route params are caller-controlled and cannot authenticate a match.
  const trustedMatch = false;
  const status = getDisplayStatus(
    result?.verification?.status ?? result?.status
  );

  const statusColor =
    status === "VERIFIED"
      ? "#16734A"
      : status === "SUSPICIOUS"
        ? "#B45309"
        : "#64748B";

  const statusBackground =
    status === "VERIFIED"
      ? "#DCFCE7"
      : status === "SUSPICIOUS"
        ? "#FEF3C7"
        : "#F1F5F9";

  const statusDescription =
    status === "VERIFIED"
      ? "A trusted transaction record matched this payment."
      : status === "SUSPICIOUS"
        ? "Potential inconsistencies were reported. Check the payment independently."
        : "This payment has not been confirmed by a trusted transaction record.";

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <Pressable
          onPress={() => router.replace("/")}
          style={styles.backButton}
        >
          <Text style={styles.backText}>‹  VyaparGuard</Text>
        </Pressable>

        <Text style={styles.eyebrow}>PAYMENT SECURITY</Text>
        <Text style={styles.heading}>Analysis Result</Text>
        <Text style={styles.subheading}>
          Review the findings before accepting a payment.
        </Text>

        <View style={styles.card}>
          <View style={styles.statusHeader}>
            <View
              style={[
                styles.statusDot,
                { backgroundColor: statusColor },
              ]}
            />
            <Text style={styles.statusLabel}>ANALYSIS STATUS</Text>
          </View>

          <View
            style={[
              styles.statusPill,
              { backgroundColor: statusBackground },
            ]}
          >
            <Text style={[styles.status, { color: statusColor }]}>
              {status}
            </Text>
          </View>

          <Text style={styles.description}>
            {statusDescription}
          </Text>

          <View style={styles.divider} />

          <Text style={styles.sectionTitle}>Extracted details</Text>

          <View style={styles.detailRow}>
            <Text style={styles.label}>Amount</Text>
            <Text style={styles.value}>
              {(result?.ocr?.amount ?? result?.extracted?.amount) != null
                ? `${result?.ocr?.currency ?? result?.extracted?.currency ?? '₹'}${result?.ocr?.amount ?? result?.extracted?.amount}`
                : "Not available"}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.label}>Transaction ID</Text>
            <Text style={styles.value}>
              {result?.ocr?.transaction_id ||
                result?.extracted?.transaction_id ||
                "Not available"}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.label}>UPI reference</Text>
            <Text style={styles.value}>
              {result?.ocr?.upi_reference ||
                result?.extracted?.upi_reference ||
                result?.extracted?.reference ||
                "Not available"}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.label}>Payee</Text>
            <Text style={styles.value}>
              {result?.ocr?.payee || result?.extracted?.payee || "Not available"}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.label}>Payment date</Text>
            <Text style={styles.value}>
              {result?.ocr?.date || result?.extracted?.date || "Not available"}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.label}>Payment time</Text>
            <Text style={styles.value}>
              {result?.ocr?.time || result?.extracted?.time || "Not available"}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.label}>Displayed payment status (from image)</Text>
            <Text style={styles.value}>
              {result?.ocr?.displayed_status ||
                result?.extracted?.displayed_status ||
                "Not available"}
            </Text>
          </View>

          {typeof result?.ocr?.confidence === "number" && (
            <View style={styles.detailRow}>
              <Text style={styles.label}>OCR confidence</Text>
              <Text style={styles.value}>
                {(result.ocr.confidence * 100).toFixed(1)}%
              </Text>
            </View>
          )}

          <View style={styles.detailRow}>
            <Text style={styles.label}>Trusted record match</Text>
            <Text style={styles.value}>
              {trustedMatch ? "Confirmed" : "Not confirmed"}
            </Text>
          </View>

          <View style={styles.divider} />

          <Text style={styles.sectionTitle}>Findings</Text>

          {result?.forensics?.assessment && (
            <View style={styles.detailRow}>
              <Text style={styles.label}>Image forensics assessment</Text>
              <Text style={styles.value}>
                {result.forensics.assessment.replace(/_/g, " ")}
              </Text>
            </View>
          )}

          {result?.image_quality?.width != null &&
            result.image_quality.height != null && (
              <View style={styles.detailRow}>
                <Text style={styles.label}>Image dimensions</Text>
                <Text style={styles.value}>
                  {result.image_quality.width} × {result.image_quality.height}
                </Text>
              </View>
            )}

          {result?.forensics?.ela_mean != null && (
            <View style={styles.detailRow}>
              <Text style={styles.label}>ELA mean</Text>
              <Text style={styles.value}>{result.forensics.ela_mean}</Text>
            </View>
          )}

          {result?.image_quality?.sharpness_score != null && (
            <View style={styles.detailRow}>
              <Text style={styles.label}>Sharpness score</Text>
              <Text style={styles.value}>
                {result.image_quality.sharpness_score}
              </Text>
            </View>
          )}

          {result?.forensics?.indicators?.map((indicator, index) => (
            <View key={`indicator-${index}-${indicator}`} style={styles.reasonRow}>
              <Text style={styles.bullet}>•</Text>
              <Text style={styles.reason}>{indicator.replace(/_/g, " ")}</Text>
            </View>
          ))}

          {result?.ocr?.fields_missing?.length ? (
            <Text style={styles.reason}>
              Missing information: {result.ocr.fields_missing.join(", ")}
            </Text>
          ) : null}

          {result?.forensics?.limitations?.map((limitation, index) => (
            <View key={`limitation-${index}-${limitation}`} style={styles.reasonRow}>
              <Text style={styles.bullet}>•</Text>
              <Text style={styles.reason}>{limitation}</Text>
            </View>
          ))}

          {result?.errors?.map((message, index) => (
            <View key={`error-${index}-${message}`} style={styles.reasonRow}>
              <Text style={styles.bullet}>•</Text>
              <Text style={styles.reason}>{message}</Text>
            </View>
          ))}

          {(result?.reasons?.length
            ? result.reasons
            : ["No additional analysis details are available."]
          ).map((reason, index) => (
            <View key={`${index}-${reason}`} style={styles.reasonRow}>
              <Text style={styles.bullet}>•</Text>
              <Text style={styles.reason}>{reason}</Text>
            </View>
          ))}

          {result?.ocr?.raw_text ? (
            <>
              <View style={styles.divider} />
              <Text style={styles.sectionTitle}>Text read from screenshot</Text>
              <Text selectable style={styles.reason}>
                {result.ocr.raw_text}
              </Text>
            </>
          ) : null}
        </View>

        <View style={styles.warning}>
          <Text style={styles.warningTitle}>Before accepting payment</Text>
          <Text style={styles.warningText}>
            Screenshots can be edited or fabricated. Confirm receipt
            directly in your bank or UPI app. This result alone is
            not proof that money was received.
          </Text>
        </View>

        <Pressable
          style={styles.primaryButton}
          onPress={() => router.replace("/upload")}
        >
          <Text style={styles.primaryButtonText}>
            Analyze Another Screenshot
          </Text>
        </Pressable>

        <Pressable
          style={styles.secondaryButton}
          onPress={() => router.replace("/")}
        >
          <Text style={styles.secondaryButtonText}>Back to Home</Text>
        </Pressable>

        <Text style={styles.footer}>
          VyaparGuard · Safer payment decisions
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F8FAFC",
  },
  content: {
    padding: 22,
    paddingBottom: 36,
  },
  backButton: {
    alignSelf: "flex-start",
    paddingVertical: 8,
    marginBottom: 24,
  },
  backText: {
    color: "#176B55",
    fontSize: 15,
    fontWeight: "700",
  },
  eyebrow: {
    color: "#176B55",
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 2,
  },
  heading: {
    fontSize: 29,
    fontWeight: "800",
    color: "#102A43",
    marginTop: 8,
  },
  subheading: {
    color: "#64748B",
    fontSize: 14,
    lineHeight: 21,
    marginTop: 8,
    marginBottom: 22,
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  statusHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusLabel: {
    color: "#64748B",
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1,
  },
  statusPill: {
    alignSelf: "flex-start",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
    marginTop: 14,
  },
  status: {
    fontSize: 20,
    fontWeight: "800",
  },
  description: {
    color: "#475569",
    fontSize: 14,
    lineHeight: 22,
    marginTop: 14,
  },
  divider: {
    height: 1,
    backgroundColor: "#E8EEF2",
    marginVertical: 20,
  },
  sectionTitle: {
    color: "#102A43",
    fontSize: 15,
    fontWeight: "800",
    marginBottom: 12,
  },
  detailRow: {
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
  },
  label: {
    color: "#64748B",
    fontSize: 12,
    marginBottom: 5,
  },
  value: {
    color: "#102A43",
    fontSize: 14,
    fontWeight: "700",
  },
  reasonRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginTop: 8,
  },
  bullet: {
    color: "#176B55",
    fontSize: 16,
    marginRight: 9,
  },
  reason: {
    flex: 1,
    color: "#475569",
    fontSize: 13,
    lineHeight: 20,
  },
  warning: {
    backgroundColor: "#FFF5DE",
    borderRadius: 15,
    padding: 16,
    marginTop: 18,
  },
  warningTitle: {
    color: "#8A5A00",
    fontSize: 14,
    fontWeight: "800",
    marginBottom: 7,
  },
  warningText: {
    color: "#725B32",
    fontSize: 12,
    lineHeight: 20,
  },
  primaryButton: {
    backgroundColor: "#176B55",
    padding: 17,
    borderRadius: 14,
    alignItems: "center",
    marginTop: 20,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontWeight: "800",
    fontSize: 14,
  },
  secondaryButton: {
    padding: 16,
    alignItems: "center",
    marginTop: 5,
  },
  secondaryButtonText: {
    color: "#176B55",
    fontWeight: "700",
  },
  footer: {
    textAlign: "center",
    color: "#94A3B8",
    fontSize: 11,
    marginTop: 20,
  },
});
