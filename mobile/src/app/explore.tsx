
import React from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
} from "react-native";

export default function ExploreScreen() {
  const checks = [
    {
      number: "01",
      title: "Screenshot inspection",
      description:
        "Look for suspicious visual inconsistencies and signs that payment details may have been altered.",
      tag: "IMAGE CHECKS",
    },
    {
      number: "02",
      title: "Transaction detail extraction",
      description:
        "Read available information such as the payment amount, date and transaction reference.",
      tag: "DETAIL EXTRACTION",
    },
    {
      number: "03",
      title: "Trusted record comparison",
      description:
        "Compare extracted details with an authorised transaction record when one is available.",
      tag: "PAYMENT CHECK",
    },
  ];

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.eyebrow}>VYAPARGUARD</Text>
        <Text style={styles.heading}>Security Centre</Text>
        <Text style={styles.subtitle}>
          Understand the checks that help you make safer payment decisions.
        </Text>

        <View style={styles.banner}>
          <View style={styles.bannerIcon}>
            <Text style={styles.shield}>✓</Text>
          </View>
          <Text style={styles.bannerTitle}>Verify. Then trust.</Text>
          <Text style={styles.bannerText}>
            A payment screenshot is not proof that money has reached your
            account. Always confirm the transaction independently.
          </Text>
        </View>

        <Text style={styles.sectionTitle}>What VyaparGuard checks</Text>

        {checks.map((item) => (
          <View style={styles.card} key={item.number}>
            <View style={styles.cardTop}>
              <Text style={styles.number}>{item.number}</Text>
              <Text style={styles.tag}>{item.tag}</Text>
            </View>
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.cardDescription}>{item.description}</Text>
          </View>
        ))}

        <Text style={styles.sectionTitle}>Safety checklist</Text>

        <View style={styles.checklist}>
          <Text style={styles.checkItem}>
            ✓  Open your bank or UPI app directly.
          </Text>
          <Text style={styles.checkItem}>
            ✓  Confirm the amount in your transaction history.
          </Text>
          <Text style={styles.checkItem}>
            ✓  Never rely only on a screenshot or SMS.
          </Text>
          <Text style={styles.checkItem}>
            ✓  Investigate mismatched or repeated reference IDs.
          </Text>
        </View>

        <Text style={styles.disclaimer}>
          Feature note: screenshot analysis and trusted-record comparison
          depend on the backend checks that are implemented and available.
        </Text>

        <Text style={styles.footer}>
          VyaparGuard · Payment verification assistance
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
    paddingBottom: 40,
  },
  eyebrow: {
    color: "#176B55",
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 2,
    marginTop: 8,
  },
  heading: {
    color: "#102A43",
    fontSize: 29,
    fontWeight: "800",
    marginTop: 8,
  },
  subtitle: {
    color: "#64748B",
    fontSize: 14,
    lineHeight: 22,
    marginTop: 9,
    marginBottom: 22,
  },
  banner: {
    backgroundColor: "#E4F3ED",
    borderRadius: 20,
    padding: 21,
    marginBottom: 28,
  },
  bannerIcon: {
    width: 45,
    height: 45,
    borderRadius: 14,
    backgroundColor: "#176B55",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  shield: {
    color: "#FFFFFF",
    fontSize: 26,
    fontWeight: "800",
  },
  bannerTitle: {
    color: "#102A43",
    fontSize: 21,
    fontWeight: "800",
  },
  bannerText: {
    color: "#46645A",
    fontSize: 13,
    lineHeight: 21,
    marginTop: 8,
  },
  sectionTitle: {
    color: "#102A43",
    fontSize: 19,
    fontWeight: "800",
    marginBottom: 14,
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E8EEF2",
    padding: 17,
    marginBottom: 12,
  },
  cardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 13,
  },
  number: {
    color: "#176B55",
    fontSize: 17,
    fontWeight: "800",
  },
  tag: {
    color: "#176B55",
    backgroundColor: "#E4F3ED",
    overflow: "hidden",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 5,
    fontSize: 9,
    fontWeight: "800",
  },
  cardTitle: {
    color: "#102A43",
    fontSize: 15,
    fontWeight: "800",
  },
  cardDescription: {
    color: "#64748B",
    fontSize: 13,
    lineHeight: 20,
    marginTop: 7,
  },
  checklist: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E8EEF2",
    padding: 17,
    marginBottom: 20,
  },
  checkItem: {
    color: "#334155",
    fontSize: 13,
    lineHeight: 21,
    marginVertical: 6,
  },
  disclaimer: {
    color: "#725B32",
    backgroundColor: "#FFF5DE",
    padding: 14,
    borderRadius: 12,
    fontSize: 12,
    lineHeight: 19,
  },
  footer: {
    color: "#94A3B8",
    textAlign: "center",
    fontSize: 11,
    marginTop: 24,
  },
});
