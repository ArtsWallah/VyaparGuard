import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system/legacy";
import { router } from "expo-router";

const API_URL = "http://172.22.63.92:8000";
const MAX_APK_SIZE = 100 * 1024 * 1024;

type APKAsset = {
  uri: string;
  name: string;
  mimeType?: string;
  size?: number;
};

type APKFinding = {
  rule_id: string;
  severity: string;
  explanation: string;
  evidence?: Record<string, unknown>;
};

type APKResult = {
  analysis_id?: string;
  analyzed_at?: string;
  status?: "COMPLETE" | "PARTIAL" | "FAILED";
  filename?: string;
  sha256?: string;
  metadata?: {
    package_name?: string | null;
    version_name?: string | null;
    version_code?: number | string | null;
    permissions?: string[];
    signing?: {
      status?: string;
      schemes?: string[];
      trust_validation?: string;
    };
  };
  findings?: APKFinding[];
  parsing_errors?: string[];
  limitations?: string[];
  recommended_next_steps?: string[];
  detail?: string | { message?: string };
};

function formatLabel(value?: string): string {
  return (value || "Unavailable").replace(/_/g, " ");
}

export default function APKAnalysisScreen() {
  const [asset, setAsset] = useState<APKAsset | null>(null);
  const [result, setResult] = useState<APKResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function chooseAPK() {
    setError(null);
    setResult(null);
    try {
      const picked = await DocumentPicker.getDocumentAsync({
        type: "application/vnd.android.package-archive",
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (picked.canceled || !picked.assets?.length) return;
      const selected = picked.assets[0];
      if (!selected.name.toLowerCase().endsWith(".apk")) {
        setError("Choose a file with the .apk extension.");
        return;
      }
      if (selected.size && selected.size > MAX_APK_SIZE) {
        setError("The APK exceeds the 100 MB upload limit.");
        return;
      }
      setAsset({
        uri: selected.uri,
        name: selected.name,
        mimeType: selected.mimeType,
        size: selected.size,
      });
    } catch (pickError) {
      setError(pickError instanceof Error ? pickError.message : "APK selection failed.");
    }
  }

  async function analyzeAPK() {
    if (!asset) return;
    setLoading(true);
    setError(null);
    try {
      const mimeType = asset.mimeType || "application/vnd.android.package-archive";
      let responseStatus: number;
      let responseText: string;

      if (Platform.OS !== "web") {
        try {
          const upload = await FileSystem.uploadAsync(
            `${API_URL}/api/v1/apk/analyze`,
            asset.uri,
            {
              httpMethod: "POST",
              uploadType: FileSystem.FileSystemUploadType.MULTIPART,
              fieldName: "apk",
              mimeType,
            }
          );
          responseStatus = upload.status;
          responseText = upload.body;
        } catch {
          const formData = new FormData();
          formData.append("apk", {
            uri: asset.uri,
            name: asset.name,
            type: mimeType,
          } as unknown as Blob);
          const response = await fetch(`${API_URL}/api/v1/apk/analyze`, {
            method: "POST",
            body: formData,
          });
          responseStatus = response.status;
          responseText = await response.text();
        }
      } else {
        const formData = new FormData();
        const blob = await (await fetch(asset.uri)).blob();
        formData.append("apk", blob, asset.name);
        const response = await fetch(`${API_URL}/api/v1/apk/analyze`, {
          method: "POST",
          body: formData,
        });
        responseStatus = response.status;
        responseText = await response.text();
      }

      const payload = JSON.parse(responseText) as APKResult;
      if (responseStatus < 200 || responseStatus >= 300) {
        const detail = payload.detail;
        throw new Error(
          typeof detail === "string"
            ? detail
            : detail?.message || `APK analysis failed (HTTP ${responseStatus}).`
        );
      }
      setResult(payload);
    } catch (analysisError) {
      setError(
        analysisError instanceof Error
          ? analysisError.message
          : "APK analysis failed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Text style={styles.backText}>‹ Back</Text>
        </Pressable>
        <Text style={styles.eyebrow}>VYAPARGUARD / APK SCREENING</Text>
        <Text style={styles.title}>Inspect an Android APK</Text>
        <Text style={styles.description}>
          This performs preliminary static screening only. The APK is never installed,
          launched, or executed.
        </Text>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Choose APK</Text>
          <Text style={styles.hint}>Maximum size: 100 MB. APKs are not stored permanently.</Text>
          <Pressable style={styles.secondaryButton} onPress={() => void chooseAPK()} disabled={loading}>
            <Text style={styles.secondaryText}>{asset ? "Choose another APK" : "Choose APK file"}</Text>
          </Pressable>
          {asset ? <Text style={styles.fileName}>{asset.name}</Text> : null}
        </View>

        {asset ? (
          <Pressable style={styles.primaryButton} onPress={() => void analyzeAPK()} disabled={loading}>
            {loading ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.primaryText}>Run static screening</Text>}
          </Pressable>
        ) : null}

        {error ? (
          <View style={styles.errorCard}>
            <Text style={styles.errorTitle}>Analysis unavailable</Text>
            <Text style={styles.body}>{error}</Text>
            <Pressable style={styles.retryButton} onPress={() => void chooseAPK()}>
              <Text style={styles.retryText}>Try another file</Text>
            </Pressable>
          </View>
        ) : null}

        {result ? (
          <View style={styles.resultArea}>
            <View style={styles.resultHeader}>
              <Text style={styles.sectionTitle}>Screening result</Text>
              <Text style={styles.status}>{formatLabel(result.status)}</Text>
            </View>
            <Text style={styles.body}>
              {result.metadata?.package_name || "Package name unavailable"}
            </Text>
            <Text style={styles.hash} numberOfLines={2}>SHA-256: {result.sha256}</Text>
            {result.findings?.length ? (
              result.findings.map((finding) => (
                <View style={styles.finding} key={finding.rule_id}>
                  <View style={styles.findingHeader}>
                    <Text style={styles.findingRule}>{finding.rule_id.replace(/_/g, " ")}</Text>
                    <Text style={styles.findingSeverity}>{finding.severity}</Text>
                  </View>
                  <Text style={styles.body}>{finding.explanation}</Text>
                </View>
              ))
            ) : (
              <View style={styles.okCard}>
                <Text style={styles.body}>No configured screening rules triggered.</Text>
              </View>
            )}
            <Text style={styles.limitationsTitle}>Limitations</Text>
            {(result.limitations || []).map((limitation) => (
              <Text style={styles.bullet} key={limitation}>• {limitation}</Text>
            ))}
            <View style={styles.warningCard}>
              <Text style={styles.warningTitle}>Do not install based on this result</Text>
              <Text style={styles.body}>
                A clean static screen does not prove that an APK is safe. Check the source,
                publisher, and signing information before installation.
              </Text>
            </View>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#F8FAFC" },
  container: { padding: 22, paddingBottom: 42 },
  backButton: { alignSelf: "flex-start", paddingVertical: 8 },
  backText: { color: "#176B55", fontSize: 17, fontWeight: "700" },
  eyebrow: { color: "#176B55", fontSize: 11, fontWeight: "800", letterSpacing: 1.2, marginTop: 16 },
  title: { color: "#102A43", fontSize: 30, lineHeight: 37, fontWeight: "800", marginTop: 8 },
  description: { color: "#64748B", fontSize: 15, lineHeight: 22, marginTop: 10, marginBottom: 20 },
  card: { backgroundColor: "#FFFFFF", borderRadius: 16, borderWidth: 1, borderColor: "#E2E8F0", padding: 17, marginBottom: 14 },
  sectionTitle: { color: "#102A43", fontSize: 19, fontWeight: "800" },
  hint: { color: "#64748B", fontSize: 13, lineHeight: 19, marginTop: 8 },
  secondaryButton: { borderWidth: 1, borderColor: "#176B55", borderRadius: 12, padding: 14, alignItems: "center", marginTop: 16 },
  secondaryText: { color: "#176B55", fontSize: 14, fontWeight: "800" },
  fileName: { color: "#475569", fontSize: 13, marginTop: 12 },
  primaryButton: { backgroundColor: "#176B55", borderRadius: 13, padding: 16, alignItems: "center", marginBottom: 14 },
  primaryText: { color: "#FFFFFF", fontSize: 15, fontWeight: "800" },
  errorCard: { backgroundColor: "#FFF5F5", borderRadius: 16, padding: 17, marginBottom: 14 },
  errorTitle: { color: "#B42318", fontSize: 17, fontWeight: "800" },
  retryButton: { alignSelf: "flex-start", paddingVertical: 12 },
  retryText: { color: "#B42318", fontSize: 14, fontWeight: "800" },
  resultArea: { marginTop: 8 },
  resultHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  status: { color: "#176B55", fontSize: 13, fontWeight: "800" },
  hash: { color: "#64748B", fontSize: 11, lineHeight: 16, marginTop: 10 },
  finding: { backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 14, padding: 15, marginTop: 10 },
  findingHeader: { flexDirection: "row", justifyContent: "space-between", gap: 8 },
  findingRule: { color: "#102A43", fontSize: 13, fontWeight: "800", flex: 1 },
  findingSeverity: { color: "#B54708", fontSize: 12, fontWeight: "800" },
  okCard: { backgroundColor: "#E4F3ED", borderRadius: 14, padding: 15, marginTop: 10 },
  limitationsTitle: { color: "#102A43", fontSize: 16, fontWeight: "800", marginTop: 18 },
  bullet: { color: "#64748B", fontSize: 13, lineHeight: 19, marginTop: 7 },
  warningCard: { backgroundColor: "#FFF8E7", borderRadius: 14, padding: 15, marginTop: 16 },
  warningTitle: { color: "#9A6700", fontSize: 15, fontWeight: "800", marginBottom: 7 },
  body: { color: "#475569", fontSize: 14, lineHeight: 20, marginTop: 7 },
});
