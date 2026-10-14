
import React from "react";
import { SafeAreaView, ScrollView, View, Text, StyleSheet, Pressable } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

type ScanResult = {
    scan_id: string;
    status: "VERIFIED" | "SUSPICIOUS" | "UNVERIFIED";
    extracted?: {
        amount?: number | null;
        transaction_id?: string | null;
        date?: string | null;
    };
    reasons?: string[];
    verification_source?: string;
};

export default function ResultScreen() {
    const router = useRouter();
    const params = useLocalSearchParams<{ result?: string }>();

    let result: ScanResult | null = null;

    try {
        if (typeof params.result === "string") {
            result = JSON.parse(params.result) as ScanResult;
        }
    } catch {
        result = null;
    }

    const status = result?.status ?? "UNVERIFIED";

    const statusColor =
        status === "VERIFIED"
            ? "#176B55"
            : status === "SUSPICIOUS"
                ? "#B45309"
                : "#64748B";

    return (
        <SafeAreaView style={styles.container}>
            <ScrollView contentContainerStyle={styles.content}>
                <Text style={styles.heading}>Analysis Result</Text>

                <View style={styles.card}>
                    <Text style={[styles.status, { color: statusColor }]}>{status}</Text>
                    <Text style={styles.description}>
                        {status === "VERIFIED"
                            ? "A trusted transaction record confirmed this payment."
                            : status === "SUSPICIOUS"
                                ? "Potential inconsistencies require further checking."
                                : "The payment has not been confirmed by a trusted record."}
                    </Text>

                    <View style={styles.divider} />

                    <Text style={styles.label}>Amount</Text>
                    <Text style={styles.value}>
                        {result?.extracted?.amount != null
                            ? `₹${result.extracted.amount}`
                            : "Not extracted"}
                    </Text>

                    <Text style={styles.label}>Transaction ID</Text>
                    <Text style={styles.value}>
                        {result?.extracted?.transaction_id || "Not extracted"}
                    </Text>

                    <Text style={styles.label}>Date</Text>
                    <Text style={styles.value}>
                        {result?.extracted?.date || "Not extracted"}
                    </Text>

                    <Text style={styles.label}>Reasons</Text>
                    {(result?.reasons?.length
                        ? result.reasons
                        : ["No additional details were returned."]
                    ).map((reason, index) => (
                        <Text key={`${index}-${reason}`} style={styles.reason}>
                            • {reason}
                        </Text>
                    ))}
                </View>

                <Text style={styles.warning}>
                    Always confirm receipt in your actual bank or payment account.
                    Screenshot analysis alone does not prove that money was received.
                </Text>

                <Pressable style={styles.button} onPress={() => router.replace("/")}>
                    <Text style={styles.buttonText}>Back to Home</Text>
                </Pressable>

                <Pressable
                    style={styles.secondaryButton}
                    onPress={() => router.replace("/upload")}
                >
                    <Text style={styles.secondaryText}>Analyze Another Screenshot</Text>
                </Pressable>
            </ScrollView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: "#F8FAFC" },
    content: { padding: 22, paddingBottom: 36 },
    heading: {
        fontSize: 27,
        fontWeight: "800",
        color: "#102A43",
        marginBottom: 22,
    },
    card: {
        backgroundColor: "#FFFFFF",
        borderRadius: 18,
        padding: 20,
        borderWidth: 1,
        borderColor: "#E8EEF2",
    },
    status: { fontSize: 25, fontWeight: "800" },
    description: {
        color: "#64748B",
        fontSize: 14,
        lineHeight: 22,
        marginTop: 8,
    },
    divider: { height: 1, backgroundColor: "#E8EEF2", marginVertical: 20 },
    label: {
        color: "#64748B",
        fontSize: 12,
        marginTop: 14,
        marginBottom: 4,
    },
    value: { color: "#102A43", fontSize: 15, fontWeight: "600" },
    reason: {
        color: "#475569",
        fontSize: 13,
        lineHeight: 20,
        marginTop: 6,
    },
    warning: {
        color: "#725B32",
        backgroundColor: "#FFF5DE",
        borderRadius: 14,
        padding: 15,
        lineHeight: 20,
        fontSize: 12,
        marginTop: 18,
    },
    button: {
        backgroundColor: "#176B55",
        padding: 17,
        borderRadius: 14,
        alignItems: "center",
        marginTop: 20,
    },
    buttonText: { color: "#FFFFFF", fontWeight: "700" },
    secondaryButton: {
        padding: 16,
        alignItems: "center",
        marginTop: 8,
    },
    secondaryText: { color: "#176B55", fontWeight: "700" },
});
