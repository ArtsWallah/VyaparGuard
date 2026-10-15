import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router, useLocalSearchParams } from "expo-router";

const API_URL = "http://172.22.63.92:8000";

type ScanCheck = {
  check_id: string;
  status: string;
  message: string;
  evidence?: Record<string, unknown> | null;
};

type ScanDetail = {
  scan_id: string;
  created_at?: string | null;
  status?: string;
  amount?: number | null;
  reference_available?: boolean;
  summary?: string | null;
  processing_ms?: number | null;
  demo_mode?: boolean;
  checks?: ScanCheck[];
};

function formatStatus(status?: string): string {
  return (status || "UNVERIFIED").replace(/_/g, " ");
}

function formatTimestamp(value?: string | null): string {
  if (!value) return "Time unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function formatAmount(value?: number | null): string {
  if (value === null || value === undefined) return "Amount unavailable";
  return `INR ${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

export default function HistoryDetailScreen() {
  const params = useLocalSearchParams<{ scanId?: string | string[] }>();
  const scanId = Array.isArray(params.scanId) ? params.scanId[0] : params.scanId;
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadScan = useCallback(async () => {
    if (!scanId) {
      setError("No scan ID was provided.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/scans/${encodeURIComponent(scanId)}`
      );
      const payload = (await response.json()) as ScanDetail & { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Scan details could not be loaded.");
      }
      setScan(payload);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Scan details could not be loaded."
      );
    } finally {
      setLoading(false);
    }
  }, [scanId]);

  useEffect(() => {
    void loadScan();
  }, [loadScan]);

  function confirmDelete() {
    if (!scanId) return;
    Alert.alert(
      "Delete scan record?",
      "This removes the visible history record. Duplicate-protection history may be retained.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => void deleteScan(),
        },
      ]
    );
  }

  async function deleteScan() {
    if (!scanId) return;
    setDeleting(true);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/scans/${encodeURIComponent(scanId)}`,
        { method: "DELETE" }
      );
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Scan could not be deleted.");
      }
      router.replace("/history");
    } catch (deleteError) {
      Alert.alert(
        "Delete failed",
        deleteError instanceof Error
          ? deleteError.message
          : "Scan could not be deleted."
      );
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.stateBox}>
          <ActivityIndicator size="large" color="#176B55" />
          <Text style={styles.stateText}>Loading scan details...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (error || !scan) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.stateBox}>
          <Text style={styles.eyebrow}>VYAPARGUARD / HISTORY</Text>
          <Text style={styles.stateTitle}>Details unavailable</Text>
          <Text style={styles.stateText}>{error || "Scan was not found."}</Text>
          <Pressable style={styles.primaryButton} onPress={() => void loadScan()}>
            <Text style={styles.primaryButtonText}>Retry</Text>
          </Pressable>
          <Pressable style={styles.linkButton} onPress={() => router.replace("/history")}>
            <Text style={styles.linkText}>Back to history</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Text style={styles.backText}>‹ History</Text>
        </Pressable>
        <Text style={styles.eyebrow}>VYAPARGUARD / SCAN DETAIL</Text>
        <Text style={styles.title}>{formatStatus(scan.status)}</Text>
        <Text style={styles.timestamp}>{formatTimestamp(scan.created_at)}</Text>

        <View style={styles.summaryCard}>
          <Text style={styles.amount}>{formatAmount(scan.amount)}</Text>
          <Text style={styles.reference}>
            {scan.reference_available
              ? "Payment reference recorded securely"
              : "Payment reference unavailable"}
          </Text>
          <Text style={styles.summary}>
            {scan.summary || "No explanation was recorded."}
          </Text>
          {scan.demo_mode ? <Text style={styles.demoNote}>Demo transaction data was used.</Text> : null}
        </View>

        <Text style={styles.sectionTitle}>Evidence checks</Text>
        {scan.checks?.length ? (
          scan.checks.map((check, index) => (
            <View style={styles.checkCard} key={`${check.check_id}-${index}`}>
              <View style={styles.checkHeader}>
                <Text style={styles.checkId}>{check.check_id.replace(/_/g, " ")}</Text>
                <Text style={styles.checkStatus}>{check.status}</Text>
              </View>
              <Text style={styles.checkMessage}>{check.message}</Text>
              {check.evidence ? (
                <Text style={styles.evidence}>
                  {JSON.stringify(check.evidence)}
                </Text>
              ) : null}
            </View>
          ))
        ) : (
          <View style={styles.checkCard}>
            <Text style={styles.checkMessage}>No detailed checks were recorded.</Text>
          </View>
        )}

        <Pressable
          style={[styles.deleteButton, deleting && styles.disabled]}
          disabled={deleting}
          onPress={confirmDelete}
        >
          <Text style={styles.deleteText}>{deleting ? "Deleting..." : "Delete scan record"}</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#F8FAFC" },
  container: { padding: 22, paddingBottom: 40 },
  backButton: { alignSelf: "flex-start", paddingVertical: 8 },
  backText: { color: "#176B55", fontSize: 17, fontWeight: "700" },
  eyebrow: { color: "#176B55", fontSize: 12, fontWeight: "800", letterSpacing: 1.1 },
  title: { color: "#102A43", fontSize: 30, fontWeight: "800", marginTop: 8 },
  timestamp: { color: "#64748B", fontSize: 13, marginTop: 7 },
  summaryCard: { backgroundColor: "#E4F3ED", borderRadius: 18, padding: 20, marginTop: 22 },
  amount: { color: "#102A43", fontSize: 25, fontWeight: "800" },
  reference: { color: "#46645A", fontSize: 14, marginTop: 6 },
  summary: { color: "#304E42", fontSize: 14, lineHeight: 21, marginTop: 16 },
  demoNote: { color: "#176B55", fontSize: 12, fontWeight: "700", marginTop: 12 },
  sectionTitle: { color: "#102A43", fontSize: 20, fontWeight: "800", marginTop: 26, marginBottom: 11 },
  checkCard: { backgroundColor: "#FFFFFF", borderRadius: 15, borderWidth: 1, borderColor: "#E2E8F0", padding: 16, marginBottom: 10 },
  checkHeader: { flexDirection: "row", justifyContent: "space-between", gap: 10 },
  checkId: { color: "#102A43", fontSize: 14, fontWeight: "800", flex: 1 },
  checkStatus: { color: "#176B55", fontSize: 12, fontWeight: "800" },
  checkMessage: { color: "#475569", fontSize: 14, lineHeight: 20, marginTop: 8 },
  evidence: { color: "#64748B", fontSize: 11, lineHeight: 16, marginTop: 9 },
  deleteButton: { borderWidth: 1, borderColor: "#B42318", borderRadius: 13, padding: 15, alignItems: "center", marginTop: 18 },
  deleteText: { color: "#B42318", fontSize: 14, fontWeight: "800" },
  disabled: { opacity: 0.5 },
  stateBox: { flex: 1, justifyContent: "center", alignItems: "center", padding: 25 },
  stateTitle: { color: "#102A43", fontSize: 20, fontWeight: "800", textAlign: "center", marginTop: 12 },
  stateText: { color: "#64748B", fontSize: 14, lineHeight: 21, textAlign: "center", marginTop: 8 },
  primaryButton: { backgroundColor: "#176B55", borderRadius: 13, paddingHorizontal: 20, paddingVertical: 13, marginTop: 18 },
  primaryButtonText: { color: "#FFFFFF", fontSize: 14, fontWeight: "800" },
  linkButton: { padding: 14, marginTop: 4 },
  linkText: { color: "#176B55", fontSize: 14, fontWeight: "800" },
});
