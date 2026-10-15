
import { useMemo } from "react";
import {
    SafeAreaView,
    ScrollView,
    StyleSheet,
    Text,
    Pressable,
    View,
} from "react-native";
import { router, useLocalSearchParams } from "expo-router";

type PaymentOCR = {
    raw_text?: string;
    confidence?: number | null;
    amount?: number | null;
    currency?: string | null;
    date?: string | null;
    time?: string | null;
    timestamp?: string | null;
    transaction_id?: string | null;
    upi_reference?: string | null;
    reference?: string | null;
    payee?: string | null;
    displayed_status?: string | null;
    fields_missing?: string[];
};

type ScanResult = {
    schema_version?: string;
    scan_id?: string;
    status?: string;
    extracted?: {
        amount?: number | null;
        transaction_id?: string | null;
        upi_reference?: string | null;
        reference?: string | null;
        date?: string | null;
        time?: string | null;
        timestamp?: string | null;
        payee?: string | null;
        currency?: string | null;
        displayed_status?: string | null;
    };
    reasons?: string[];
    verification_source?: string;
    file?: {
        filename?: string;
        content_type?: string;
        size_bytes?: number;
        [key: string]: unknown;
    };
    ocr?: PaymentOCR;
    image_quality?: {
        width?: number;
        height?: number;
        sharpness_score?: number;
    };
    forensics?: {
        ela_mean?: number | null;
        indicators?: string[];
        assessment?: string;
        limitations?: string[];
    };
    errors?: string[];
    verification?: {
        status?: string;
        source?: string;
        reason?: string;
    };
    recipient_verification?: {
        qr?: {
            status?: string;
            explanation?: string;
            expected_recipient?: string | null;
            destination?: {
                payee_identifier?: string | null;
                payee_name?: string | null;
                amount?: string | number | null;
                reference?: string | null;
            } | null;
        };
        payment_message?: {
            status?: string;
            explanation?: string;
            untrusted?: boolean;
        } | null;
    };
};

function displayValue(value: string | number | null | undefined): string {
    if (value === null || value === undefined || value === "") {
        return "Not detected";
    }

    return String(value);
}

function formatAmount(
    amount: number | null | undefined,
    currency?: string | null
): string {
    if (amount === null || amount === undefined) return "Not detected";

    const currencyCode = currency || "INR";

    if (currencyCode === "INR") {
        return `₹${amount.toLocaleString("en-IN", {
            maximumFractionDigits: 2,
        })}`;
    }

    return `${currencyCode} ${amount.toLocaleString("en-IN", {
        maximumFractionDigits: 2,
    })}`;
}

function formatLabel(value?: string): string {
    if (!value) return "Unavailable";

    return value
        .replace(/_/g, " ")
        .toLowerCase()
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function ResultScreen() {
    const params = useLocalSearchParams<{ result?: string | string[] }>();

    const resultString = Array.isArray(params.result)
        ? params.result[0]
        : params.result;

    const parsed = useMemo(() => {
        if (!resultString) {
            return {
                data: null as ScanResult | null,
                error: "No analysis result was provided.",
            };
        }

        try {
            let jsonString = resultString;
            try {
                jsonString = decodeURIComponent(resultString);
            } catch {
                // If decodeURIComponent fails, fallback to raw string
            }

            return {
                data: JSON.parse(jsonString) as ScanResult,
                error: null as string | null,
            };
        } catch {
            return {
                data: null as ScanResult | null,
                error: "The analysis result could not be read. Please scan again.",
            };
        }
    }, [resultString]);

    const data = parsed.data;
    const ocr = data?.ocr ?? (data?.extracted ? {
        amount: data.extracted.amount,
        currency: data.extracted.currency,
        date: data.extracted.date,
        time: data.extracted.time,
        timestamp: data.extracted.timestamp,
        transaction_id: data.extracted.transaction_id,
        upi_reference: data.extracted.upi_reference,
        reference: data.extracted.reference,
        payee: data.extracted.payee,
        displayed_status: data.extracted.displayed_status,
        fields_missing: [],
    } : undefined);
    const forensics = data?.forensics;
    const verification = data?.verification;
    const quality = data?.image_quality;
    const recipientVerification = data?.recipient_verification;

    if (!data) {
        return (
            <SafeAreaView style={styles.safeArea}>
                <View style={styles.errorContainer}>
                    <Text style={styles.eyebrow}>VYAPARGUARD</Text>
                    <Text style={styles.title}>Result unavailable</Text>
                    <Text style={styles.bodyText}>{parsed.error}</Text>
                    <Pressable
                        onPress={() => router.replace("/upload")}
                        style={styles.primaryButton}
                    >
                        <Text style={styles.primaryButtonText}>Scan again</Text>
                    </Pressable>
                </View>
            </SafeAreaView>
        );
    }

    const verificationStatus =
        verification?.status || data?.status || "UNVERIFIED";

    return (
        <SafeAreaView style={styles.safeArea}>
            <ScrollView contentContainerStyle={styles.container}>
                <Pressable
                    onPress={() => router.replace("/upload")}
                    style={styles.backButton}
                >
                    <Text style={styles.backText}>‹ Scan another screenshot</Text>
                </Pressable>

                <Text style={styles.eyebrow}>VYAPARGUARD / SCAN REPORT</Text>
                <Text style={styles.title}>Analysis results</Text>
                <Text style={styles.subtitle}>
                    Extracted information and image inspection findings.
                </Text>

                <View style={styles.verificationCard}>
                    <Text style={styles.sectionEyebrow}>PAYMENT VERIFICATION</Text>
                    <Text style={styles.verificationStatus}>
                        {verificationStatus.replace(/_/g, " ")}
                    </Text>
                    <Text style={styles.bodyText}>
                        {verification?.reason ||
                            "No trusted transaction source confirmation was provided."}
                    </Text>
                    <View style={styles.sourceRow}>
                        <Text style={styles.sourceLabel}>Verification source</Text>
                        <Text style={styles.sourceValue}>
                            {displayValue(verification?.source)}
                        </Text>
                    </View>
                </View>

                {recipientVerification ? (
                    <View style={styles.recipientCard}>
                        <Text style={styles.sectionTitle}>Recipient and message checks</Text>
                        <DetailRow
                            label="QR outcome"
                            value={formatLabel(recipientVerification.qr?.status)}
                        />
                        <DetailRow
                            label="QR recipient"
                            value={displayValue(
                                recipientVerification.qr?.destination?.payee_identifier
                            )}
                        />
                        <DetailRow
                            label="Expected recipient"
                            value={displayValue(
                                recipientVerification.qr?.expected_recipient
                            )}
                        />
                        <Text style={styles.bodyText}>
                            {recipientVerification.qr?.explanation ||
                                "No QR destination result was provided."}
                        </Text>
                        {recipientVerification.payment_message ? (
                            <>
                                <Text style={styles.subheading}>Payment message</Text>
                                <Text style={styles.bodyText}>
                                    {formatLabel(recipientVerification.payment_message.status)}
                                    {recipientVerification.payment_message.untrusted
                                        ? " · untrusted evidence"
                                        : ""}
                                </Text>
                                <Text style={styles.bodyText}>
                                    {recipientVerification.payment_message.explanation}
                                </Text>
                            </>
                        ) : null}
                        <Text style={styles.limitationsText}>
                            A QR match or message agreement identifies consistency only;
                            it does not prove payment settlement.
                        </Text>
                    </View>
                ) : null}

                <View style={styles.amountCard}>
                    <Text style={styles.mutedLabel}>AMOUNT READ FROM SCREENSHOT</Text>
                    <Text style={styles.amount}>
                        {formatAmount(ocr?.amount, ocr?.currency)}
                    </Text>
                    <Text style={styles.bodyText}>
                        Displayed status: {displayValue(ocr?.displayed_status)}
                    </Text>
                </View>

                <View style={styles.card}>
                    <Text style={styles.sectionTitle}>Extracted transaction details</Text>
                    <DetailRow label="Payee" value={displayValue(ocr?.payee)} />
                    <DetailRow
                        label="Transaction ID"
                        value={displayValue(ocr?.transaction_id)}
                    />
                    <DetailRow
                        label="UPI reference"
                        value={displayValue(ocr?.upi_reference ?? ocr?.reference)}
                    />
                    <DetailRow label="Date" value={displayValue(ocr?.date)} />
                    <DetailRow label="Time" value={displayValue(ocr?.time)} />
                    <DetailRow
                        label="OCR confidence"
                        value={
                            typeof ocr?.confidence === "number"
                                ? `${(ocr.confidence * 100).toFixed(1)}%`
                                : "Unavailable"
                        }
                        last
                    />
                </View>

                <View style={styles.card}>
                    <Text style={styles.sectionTitle}>Image forensics</Text>
                    <DetailRow
                        label="Assessment"
                        value={formatLabel(forensics?.assessment)}
                    />
                    <DetailRow
                        label="ELA mean"
                        value={displayValue(forensics?.ela_mean)}
                    />
                    <DetailRow
                        label="Image dimensions"
                        value={
                            quality?.width && quality?.height
                                ? `${quality.width} × ${quality.height} px`
                                : "Unavailable"
                        }
                    />
                    <DetailRow
                        label="Sharpness score"
                        value={displayValue(quality?.sharpness_score)}
                        last
                    />

                    <Text style={styles.subheading}>Indicators</Text>
                    {forensics?.indicators?.length ? (
                        forensics.indicators.map((indicator, index) => (
                            <Text key={`${indicator}-${index}`} style={styles.bulletText}>
                                • {indicator}
                            </Text>
                        ))
                    ) : (
                        <Text style={styles.bodyText}>
                            No manipulation indicators were reported by this analysis.
                        </Text>
                    )}

                    {!!forensics?.limitations?.length && (
                        <>
                            <Text style={styles.subheading}>Limitations</Text>
                            {forensics.limitations.map((limitation, index) => (
                                <Text key={`${limitation}-${index}`} style={styles.bulletText}>
                                    • {limitation}
                                </Text>
                            ))}
                        </>
                    )}
                </View>

                {!!ocr?.fields_missing?.length && (
                    <View style={styles.warningCard}>
                        <Text style={styles.warningTitle}>Missing information</Text>
                        <Text style={styles.bodyText}>
                            {ocr.fields_missing.join(", ")}
                        </Text>
                    </View>
                )}

                {!!data.errors?.length && (
                    <View style={styles.warningCard}>
                        <Text style={styles.warningTitle}>Processing messages</Text>
                        {data.errors.map((error, index) => (
                            <Text key={`${error}-${index}`} style={styles.bodyText}>
                                • {error}
                            </Text>
                        ))}
                    </View>
                )}

                {!!ocr?.raw_text && (
                    <View style={styles.card}>
                        <Text style={styles.sectionTitle}>Raw OCR text</Text>
                        <Text selectable style={styles.rawText}>
                            {ocr.raw_text}
                        </Text>
                    </View>
                )}

                <View style={styles.disclaimer}>
                    <Text style={styles.disclaimerTitle}>Do not rely on the screenshot alone</Text>
                    <Text style={styles.disclaimerText}>
                        A screenshot can display “Payment Successful” even when the
                        transaction has not been received. OCR and image forensics are
                        screening tools, not proof of payment. Confirm the transaction
                        through your bank or a trusted transaction source.
                    </Text>
                </View>

                <Pressable
                    onPress={() => router.replace("/upload")}
                    style={styles.primaryButton}
                >
                    <Text style={styles.primaryButtonText}>Analyze another screenshot</Text>
                </Pressable>
            </ScrollView>
        </SafeAreaView>
    );
}

function DetailRow({
    label,
    value,
    last = false,
}: {
    label: string;
    value: string;
    last?: boolean;
}) {
    return (
        <View style={[styles.detailRow, !last && styles.detailBorder]}>
            <Text style={styles.detailLabel}>{label}</Text>
            <Text selectable style={styles.detailValue}>
                {value}
            </Text>
        </View>
    );
}

const styles = StyleSheet.create({
    safeArea: {
        flex: 1,
        backgroundColor: "#F7F8FA",
    },
    container: {
        padding: 20,
        paddingBottom: 40,
    },
    errorContainer: {
        flex: 1,
        padding: 24,
        justifyContent: "center",
    },
    backButton: {
        alignSelf: "flex-start",
        paddingVertical: 8,
        marginBottom: 22,
    },
    backText: {
        color: "#344054",
        fontSize: 14,
        fontWeight: "700",
    },
    eyebrow: {
        color: "#18794E",
        fontSize: 11,
        fontWeight: "800",
        letterSpacing: 1.4,
        marginBottom: 9,
    },
    title: {
        color: "#101828",
        fontSize: 28,
        fontWeight: "800",
        marginBottom: 8,
    },
    subtitle: {
        color: "#667085",
        fontSize: 14,
        lineHeight: 21,
        marginBottom: 22,
    },
    verificationCard: {
        backgroundColor: "#FFF8E7",
        borderColor: "#F0D58A",
        borderWidth: 1,
        borderRadius: 15,
        padding: 17,
        marginBottom: 15,
    },
    sectionEyebrow: {
        color: "#805B10",
        fontSize: 10,
        fontWeight: "800",
        letterSpacing: 1.2,
        marginBottom: 8,
    },
    verificationStatus: {
        color: "#805B10",
        fontSize: 24,
        fontWeight: "900",
        marginBottom: 9,
    },
    sourceRow: {
        marginTop: 14,
        paddingTop: 12,
        borderTopWidth: 1,
        borderTopColor: "#F0D58A",
    },
    sourceLabel: {
        color: "#715B2A",
        fontSize: 12,
        marginBottom: 4,
    },
    sourceValue: {
        color: "#805B10",
        fontSize: 14,
        fontWeight: "700",
    },
    amountCard: {
        backgroundColor: "#FFFFFF",
        borderWidth: 1,
        borderColor: "#E4E7EC",
        borderRadius: 15,
        padding: 18,
        marginBottom: 15,
    },
    recipientCard: {
        backgroundColor: "#FFFFFF",
        borderRadius: 16,
        padding: 17,
        marginBottom: 15,
        borderWidth: 1,
        borderColor: "#D0E8DE",
    },
    limitationsText: {
        color: "#667085",
        fontSize: 12,
        lineHeight: 18,
        marginTop: 12,
    },
    mutedLabel: {
        color: "#667085",
        fontSize: 10,
        fontWeight: "800",
        letterSpacing: 1,
        marginBottom: 8,
    },
    amount: {
        color: "#101828",
        fontSize: 32,
        fontWeight: "900",
        marginBottom: 9,
    },
    card: {
        backgroundColor: "#FFFFFF",
        borderColor: "#E4E7EC",
        borderWidth: 1,
        borderRadius: 15,
        padding: 17,
        marginBottom: 15,
    },
    sectionTitle: {
        color: "#101828",
        fontSize: 17,
        fontWeight: "800",
        marginBottom: 12,
    },
    detailRow: {
        paddingVertical: 12,
        gap: 5,
    },
    detailBorder: {
        borderBottomWidth: 1,
        borderBottomColor: "#EAECF0",
    },
    detailLabel: {
        color: "#667085",
        fontSize: 12,
    },
    detailValue: {
        color: "#101828",
        fontSize: 14,
        fontWeight: "600",
        lineHeight: 21,
    },
    subheading: {
        color: "#344054",
        fontSize: 13,
        fontWeight: "800",
        marginTop: 16,
        marginBottom: 8,
    },
    bodyText: {
        color: "#667085",
        fontSize: 13,
        lineHeight: 20,
    },
    bulletText: {
        color: "#475467",
        fontSize: 13,
        lineHeight: 20,
        marginBottom: 6,
    },
    warningCard: {
        backgroundColor: "#FFF8E7",
        borderWidth: 1,
        borderColor: "#F0D58A",
        borderRadius: 12,
        padding: 15,
        marginBottom: 15,
    },
    warningTitle: {
        color: "#805B10",
        fontSize: 14,
        fontWeight: "800",
        marginBottom: 7,
    },
    rawText: {
        color: "#475467",
        fontSize: 12,
        lineHeight: 19,
    },
    disclaimer: {
        backgroundColor: "#EEF4FF",
        borderColor: "#C7D7FE",
        borderWidth: 1,
        borderRadius: 12,
        padding: 15,
        marginBottom: 20,
    },
    disclaimerTitle: {
        color: "#1849A9",
        fontSize: 14,
        fontWeight: "800",
        marginBottom: 7,
    },
    disclaimerText: {
        color: "#344054",
        fontSize: 13,
        lineHeight: 20,
    },
    primaryButton: {
        backgroundColor: "#157347",
        borderRadius: 12,
        minHeight: 52,
        alignItems: "center",
        justifyContent: "center",
        padding: 14,
    },
    primaryButtonText: {
        color: "#FFFFFF",
        fontSize: 14,
        fontWeight: "800",
        textAlign: "center",
    },
});
