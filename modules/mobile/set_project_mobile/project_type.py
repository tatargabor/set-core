"""Mobile (Capacitor) project type plugin for SET.

Extends WebProjectType with Capacitor-specific verification rules,
orchestration directives, and engine integration. Inherits all web
capabilities (Playwright E2E, Prisma, i18n, Next.js patterns).

Inheritance chain: MobileProjectType → WebProjectType → CoreProfile → ProjectType
"""

from pathlib import Path
from typing import List, Optional

from set_project_web import WebProjectType
from set_orch.profile_types import (
    OrchestrationDirective,
    ProjectTypeInfo,
    TemplateInfo,
    VerificationRule,
)


class MobileProjectType(WebProjectType):
    """Mobile application project type (Capacitor hybrid apps).

    Inherits all web capabilities and adds:
    - Capacitor config verification
    - cap sync post-merge directive
    - Native config serialization (ios/App/, android/app/)
    - iOS build detection
    - Mobile-specific planning rules
    """

    @property
    def info(self) -> ProjectTypeInfo:
        return ProjectTypeInfo(
            name="mobile",
            version="0.1.0",
            description="Mobile application project knowledge (Capacitor, native shells, hybrid apps)",
            parent="web",
        )

    def get_templates(self) -> List[TemplateInfo]:
        return [
            TemplateInfo(
                id="capacitor-nextjs",
                description="Capacitor + Next.js hybrid app with iOS/Android shells",
                template_dir="templates/capacitor-nextjs",
            ),
        ]

    # ── Verification Rules ────────────────────────────────────

    def get_verification_rules(self) -> List[VerificationRule]:
        parent_rules = super().get_verification_rules()

        mobile_rules = [
            VerificationRule(
                id="capacitor-config-exists",
                description="Capacitor config must exist and have valid webDir",
                check="file-exists",
                severity="warning",
                config={"pattern": "capacitor.config.ts"},
            ),
            VerificationRule(
                id="capacitor-plugin-consistency",
                description="Capacitor plugin versions in package.json should be compatible with @capacitor/core",
                check="pattern-audit",
                severity="warning",
                config={
                    "pattern": "package.json",
                    "match": r'"@capacitor/',
                },
            ),
            VerificationRule(
                id="native-entitlements-sync",
                description="iOS entitlements should match Capacitor plugin requirements",
                check="file-exists",
                severity="info",
                config={"pattern": "ios/App/App/App.entitlements"},
            ),
        ]

        return parent_rules + mobile_rules

    # ── Orchestration Directives ──────────────────────────────

    def get_orchestration_directives(self) -> List[OrchestrationDirective]:
        parent_directives = super().get_orchestration_directives()

        mobile_directives = [
            OrchestrationDirective(
                id="cap-sync-after-config",
                description="Run cap sync after Capacitor config or plugin changes",
                trigger='change-modifies-any("capacitor.config.ts", "package.json")',
                action="post-merge",
                config={"command": "npx cap sync"},
            ),
            OrchestrationDirective(
                id="no-parallel-ios-native",
                description="Serialize changes that modify iOS native project files to prevent Xcode merge conflicts",
                trigger='change-modifies("ios/App/**")',
                action="serialize",
                config={"with": 'changes-modifying("ios/App/**")'},
            ),
            OrchestrationDirective(
                id="no-parallel-android-native",
                description="Serialize changes that modify Android native project files",
                trigger='change-modifies("android/app/**")',
                action="serialize",
                config={"with": 'changes-modifying("android/app/**")'},
            ),
            OrchestrationDirective(
                id="native-config-review",
                description="Flag changes to native project config for review",
                trigger='change-modifies-any("ios/App/App/Info.plist", "ios/App/App/App.entitlements", "android/app/src/main/AndroidManifest.xml")',
                action="flag-for-review",
            ),
        ]

        return parent_directives + mobile_directives

    # ── Engine Integration ────────────────────────────────────

    def detect_build_command(self, project_path: str) -> Optional[str]:
        """Detect build command — adds cap sync for Capacitor projects."""
        p = Path(project_path)
        has_ios = (p / "ios" / "App").is_dir()
        has_android = (p / "android" / "app").is_dir()
        has_capacitor = (p / "capacitor.config.ts").is_file()

        if has_capacitor and (has_ios or has_android):
            pm = self.detect_package_manager(project_path) or "npm"
            platform = "ios" if has_ios else "android"
            return f"{pm} run build && npx cap sync {platform}"

        return super().detect_build_command(project_path)

    def planning_rules(self) -> str:
        """Load mobile-specific planning rules, prepended to web rules."""
        rules_file = Path(__file__).parent / "planning_rules.txt"
        mobile_rules = rules_file.read_text() if rules_file.is_file() else ""

        web_rules = super().planning_rules()
        if mobile_rules and web_rules:
            return mobile_rules + "\n\n" + web_rules
        return mobile_rules or web_rules

    def cross_cutting_files(self) -> List[str]:
        """Add Capacitor config to cross-cutting files."""
        parent = super().cross_cutting_files()
        return parent + [
            "capacitor.config.ts",
            "ios/App/App/Info.plist",
            "ios/App/App/App.entitlements",
        ]

    def ignore_patterns(self) -> List[str]:
        """Add native build artifacts to ignore list."""
        parent = super().ignore_patterns()
        return parent + [
            "ios/App/Pods/",
            "ios/App/build/",
            "android/app/build/",
            "android/.gradle/",
        ]

    def generated_file_patterns(self) -> List[str]:
        """Files generated by Capacitor that can be auto-resolved during merge."""
        parent = super().generated_file_patterns()
        return parent + [
            "ios/App/App/public/**",   # Capacitor copies web assets here
            "android/app/src/main/assets/public/**",
        ]

    def security_checklist(self) -> str:
        """Mobile-specific security checklist items."""
        return (
            "- [ ] API keys are not hardcoded in native source files\n"
            "- [ ] App Transport Security exceptions are justified (Info.plist)\n"
            "- [ ] Capacitor plugins request only necessary permissions\n"
            "- [ ] Share Extension validates incoming data before processing\n"
            "- [ ] App Groups data is not sensitive or is encrypted at rest"
        )
