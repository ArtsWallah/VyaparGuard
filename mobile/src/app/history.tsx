import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router } from "expo-router";

const API_URL = "http://172.22.63.92:8000";

type ScanSummary = {
  scan_id: string;
  created_at?: string | null;
  status?: string;
  amount?: number | null;
  reference_available?: boolean;
  summary?: string | null;
};

type ScanListResponse = {
  items?: ScanSummary[];
  page?: number;
  page_size?: number;
  total?: number;
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

export default function HistoryScreen() {
  const [items, setItems] = useState<ScanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/v1/scans?page=1&page_size=50`);
      const payload = (await response.json()) as ScanListResponse & {
        detail?: string;
      };
      if (!response.ok) {
        throw new Error(payload.detail || "Scan history could not be loaded.");
      }
      setItems(payload.items || []);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Scan history could not be loaded."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => void loadHistory(true)}
            tintColor="#176B55"
          />
        }
      >
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Text style={styles.backText}>‹ Back</Text>
        </Pressable>
        <Text style={styles.eyebrow}>VYAPARGUARD / HISTORY</Text>
        <Text style={styles.title}>Scan history</Text>
        <Text style={styles.subtitle}>
          Review previous evidence checks and the backend decision.
        </Text>

        {loading ? (
          <View style={styles.stateBox}>
            <ActivityIndicator size="large" color="#176B55" />
            <Text style={styles.stateText}>Loading scan history...</Text>
          </View>
        ) : error ? (
          <View style={styles.stateBox}>
            <Text style={styles.stateTitle}>History unavailable</Text>
            <Text style={styles.stateText}>{error}</Text>
            <Pressable style={styles.primaryButton} onPress={() => void loadHistory()}>
              <Text style={styles.primaryButtonText}>Retry</Text>
            </Pressable>
          </View>
        ) : items.length === 0 ? (
          <View style={styles.stateBox}>
            <Text style={styles.stateTitle}>No scans yet</Text>
            <Text style={styles.stateText}>
              Completed payment checks will appear here.
            </Text>
            <Pressable
              style={styles.primaryButton}
              onPress={() => router.replace("/upload")}
            >
              <Text style={styles.primaryButtonText}>Analyze a screenshot</Text>
            </Pressable>
          </View>
        ) : (
          <View style={styles.list}>
            {items.map((item) => (
              <Pressable
                key={item.scan_id}
                style={({ pressed }) => [styles.scanRow, pressed && styles.pressed]}
                onPress={() =>
                  router.push({
                    pathname: "/history-detail",
                    params: { scanId: item.scan_id },
                  })
                }
              >
                <View style={styles.rowTop}>
                  <Text style={styles.status}>{formatStatus(item.status)}</Text>
                  <Text style={styles.chevron}>›</Text>
                </View>
                <Text style={styles.timestamp}>{formatTimestamp(item.created_at)}</Text>
                <Text style={styles.amount}>{formatAmount(item.amount)}</Text>
                <Text style={styles.reference}>
                  {item.reference_available ? "Reference recorded" : "Reference unavailable"}
                </Text>
                <Text style={styles.summary} numberOfLines={2}>
                  {item.summary || "No summary provided."}
                </Text>
              </Pressable>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#F8FAFC" },
  container: { padding: 22, paddingBottom: 36 },
  backButton: { alignSelf: "flex-start", paddingVertical: 8 },
  backText: { color: "#176B55", fontSize: 17, fontWeight: "700" },
  eyebrow: { color: "#176B55", fontSize: 12, fontWeight: "800", letterSpacing: 1.2 },
  title: { color: "#102A43", fontSize: 32, fontWeight: "800", marginTop: 8 },
  subtitle: { color: "#64748B", fontSize: 15, lineHeight: 22, marginTop: 8, marginBottom: 22 },
  list: { gap: 12 },
  scanRow: { backgroundColor: "#FFFFFF", borderRadius: 16, padding: 17, borderWidth: 1, borderColor: "#E2E8F0" },
  pressed: { opacity: 0.75 },
  rowTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  status: { color: "#176B55", fontSize: 16, fontWeight: "800" },
  chevron: { color: "#176B55", fontSize: 28, lineHeight: 26 },
  timestamp: { color: "#64748B", fontSize: 12, marginTop: 6 },
  amount: { color: "#102A43", fontSize: 20, fontWeight: "800", marginTop: 12 },
  reference: { color: "#46645A", fontSize: 13, marginTop: 4 },
  summary: { color: "#475569", fontSize: 13, lineHeight: 19, marginTop: 10 },
  stateBox: { backgroundColor: "#FFFFFF", borderRadius: 16, padding: 24, alignItems: "center", borderWidth: 1, borderColor: "#E2E8F0" },
  stateTitle: { color: "#102A43", fontSize: 19, fontWeight: "800", textAlign: "center" },
  stateText: { color: "#64748B", fontSize: 14, lineHeight: 21, textAlign: "center", marginTop: 8 },
  primaryButton: { backgroundColor: "#176B55", borderRadius: 13, paddingHorizontal: 18, paddingVertical: 13, marginTop: 18 },
  primaryButtonText: { color: "#FFFFFF", fontSize: 14, fontWeight: "800" },
});
