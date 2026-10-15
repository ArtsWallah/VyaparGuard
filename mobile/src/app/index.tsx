
import React from 'react';
import {
  ScrollView,
  View,
  Text,
  Pressable,
  StyleSheet,
  StatusBar,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

export default function HomeScreen() {
  const router = useRouter();

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar
        barStyle="dark-content"
        backgroundColor="#F8FAFC"
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.brandContainer}>
            <Text style={styles.brand}>VyaparGuard</Text>
            <Text style={styles.subtitle}>
              Digital payment safety for every seller
            </Text>
          </View>

          <View style={styles.logo}>
            <Text style={styles.logoText}>V</Text>
          </View>
        </View>

        {/* Hero section */}
        <View style={styles.hero}>
          <View style={styles.badge}>
            <View style={styles.badgeDot} />
            <Text style={styles.badgeText}>
              SMART PAYMENT SCREENING
            </Text>
          </View>

          <View style={styles.shield}>
            <Text style={styles.shieldText}>✓</Text>
          </View>

          <Text style={styles.heroTitle}>
            Verify before you trust.
          </Text>

          <Text style={styles.heroDescription}>
            Check payment screenshots for suspicious indicators
            and compare transaction details with trusted records
            when available.
          </Text>
        </View>

        {/* Scan button */}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Analyze payment screenshot"
          style={({ pressed }) => [
            styles.primaryButton,
            pressed && styles.buttonPressed,
          ]}
          onPress={() => router.push('/scan')}
        >
          <Text style={styles.primaryButtonText}>
            Analyze Payment Screenshot
          </Text>
          <Text style={styles.buttonArrow}>→</Text>
        </Pressable>

        <Text style={styles.helperText}>
          Select a screenshot from your gallery to get started.
        </Text>

        {/* Safety notice */}
        <View style={styles.notice}>
          <View style={styles.noticeIcon}>
            <Text style={styles.noticeIconText}>!</Text>
          </View>

          <View style={styles.noticeContent}>
            <Text style={styles.noticeTitle}>
              Never trust a screenshot alone
            </Text>
            <Text style={styles.noticeText}>
              A payment image is not proof of settlement. Check
              your bank or UPI transaction history before handing
              over goods or services.
            </Text>
          </View>
        </View>

        {/* How it works */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>How it works</Text>
          <Text style={styles.sectionSubtitle}>
            Three simple steps
          </Text>
        </View>

        {[
          {
            number: '01',
            title: 'Read payment details',
            description:
              'Identify available information such as amount, date and transaction reference.',
          },
          {
            number: '02',
            title: 'Inspect for warning signs',
            description:
              'Look for potential inconsistencies and duplicate indicators where supported.',
          },
          {
            number: '03',
            title: 'Review the result',
            description:
              'Understand the available evidence and what you should check next.',
          },
        ].map((item) => (
          <View style={styles.stepCard} key={item.number}>
            <View style={styles.stepNumberContainer}>
              <Text style={styles.stepNumber}>{item.number}</Text>
            </View>

            <View style={styles.stepContent}>
              <Text style={styles.stepTitle}>{item.title}</Text>
              <Text style={styles.stepDescription}>
                {item.description}
              </Text>
            </View>
          </View>
        ))}

        {/* Demo disclosure */}
        <View style={styles.demoNotice}>
          <Text style={styles.demoTitle}>Demo mode</Text>
          <Text style={styles.demoText}>
            Some verification checks may not be implemented yet.
            Results depend on the checks actually performed by
            the connected backend.
          </Text>
        </View>

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
    backgroundColor: '#F8FAFC',
  },
  content: {
    padding: 22,
    paddingBottom: 110,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 28,
  },
  brandContainer: {
    flex: 1,
    marginRight: 12,
  },
  brand: {
    fontSize: 25,
    fontWeight: '800',
    color: '#102A43',
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 5,
  },
  logo: {
    width: 48,
    height: 48,
    borderRadius: 15,
    backgroundColor: '#176B55',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoText: {
    color: '#FFFFFF',
    fontSize: 25,
    fontWeight: '800',
  },
  hero: {
    backgroundColor: '#E4F3ED',
    borderRadius: 24,
    padding: 23,
    marginBottom: 18,
  },
  badge: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    paddingHorizontal: 11,
    paddingVertical: 7,
    marginBottom: 22,
  },
  badgeDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: '#176B55',
    marginRight: 7,
  },
  badgeText: {
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.8,
    color: '#176B55',
  },
  shield: {
    width: 56,
    height: 56,
    borderRadius: 18,
    backgroundColor: '#176B55',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 19,
  },
  shieldText: {
    fontSize: 32,
    color: '#FFFFFF',
    fontWeight: '800',
  },
  heroTitle: {
    fontSize: 28,
    lineHeight: 35,
    fontWeight: '800',
    color: '#102A43',
  },
  heroDescription: {
    color: '#46645A',
    fontSize: 14,
    lineHeight: 22,
    marginTop: 11,
  },
  primaryButton: {
    backgroundColor: '#176B55',
    borderRadius: 15,
    paddingHorizontal: 17,
    paddingVertical: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 9,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
    textAlign: 'center',
    flexShrink: 1,
  },
  buttonArrow: {
    color: '#FFFFFF',
    fontSize: 21,
    fontWeight: '600',
    marginLeft: 10,
  },
  buttonPressed: {
    opacity: 0.82,
  },
  helperText: {
    color: '#64748B',
    fontSize: 11,
    textAlign: 'center',
    marginBottom: 23,
  },
  notice: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#FFF5DE',
    borderRadius: 16,
    padding: 16,
    marginBottom: 29,
  },
  noticeIcon: {
    width: 27,
    height: 27,
    borderRadius: 14,
    backgroundColor: '#F4DCA5',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 11,
  },
  noticeIconText: {
    color: '#8A5A00',
    fontSize: 17,
    fontWeight: '800',
  },
  noticeContent: {
    flex: 1,
  },
  noticeTitle: {
    color: '#8A5A00',
    fontSize: 14,
    fontWeight: '800',
    marginBottom: 6,
  },
  noticeText: {
    color: '#725B32',
    fontSize: 12,
    lineHeight: 19,
  },
  sectionHeader: {
    marginBottom: 15,
  },
  sectionTitle: {
    fontSize: 21,
    fontWeight: '800',
    color: '#102A43',
  },
  sectionSubtitle: {
    color: '#64748B',
    fontSize: 12,
    marginTop: 4,
  },
  stepCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginBottom: 11,
    borderWidth: 1,
    borderColor: '#E8EEF2',
  },
  stepNumberContainer: {
    width: 39,
    height: 39,
    borderRadius: 12,
    backgroundColor: '#E4F3ED',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 13,
  },
  stepNumber: {
    color: '#176B55',
    fontSize: 13,
    fontWeight: '800',
  },
  stepContent: {
    flex: 1,
  },
  stepTitle: {
    color: '#102A43',
    fontSize: 14,
    fontWeight: '700',
  },
  stepDescription: {
    color: '#64748B',
    fontSize: 12,
    lineHeight: 19,
    marginTop: 5,
  },
  demoNotice: {
    backgroundColor: '#F1F5F9',
    borderRadius: 14,
    padding: 15,
    marginTop: 15,
  },
  demoTitle: {
    color: '#334155',
    fontSize: 13,
    fontWeight: '800',
    marginBottom: 5,
  },
  demoText: {
    color: '#64748B',
    fontSize: 12,
    lineHeight: 19,
  },
  footer: {
    textAlign: 'center',
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 23,
  },
});
