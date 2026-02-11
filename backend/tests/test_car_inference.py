"""Tests for car make/model/generation inference from part name and description."""

import pytest

from app.core.car_inference import infer_car_generations


class TestInferCarGenerations:
    """Test infer_car_generations returns expected (make, model, generation_name) triples."""

    def test_mkv_supra_a90(self) -> None:
        # MKV / GR Supra A90 aliases
        result = infer_car_generations(
            "Cusco Rear Chassis Power Brace MKV Supra GR A90 / A91",
            "Cusco Rear Chassis Power Brace for the 2020 GR Supra A90.",
        )
        assert ("Toyota", "Supra", "A90") in result

    def test_supra_gr_a90_from_name(self) -> None:
        result = infer_car_generations("Remark Toyota Supra GR A90 Full Titanium Cat-Back Exhaust", None)
        assert ("Toyota", "Supra", "A90") in result

    def test_a90_a91_phrase(self) -> None:
        result = infer_car_generations("KW 2 Way Clubsport Coilover Kit - MKV Supra A90 / A91", None)
        assert ("Toyota", "Supra", "A90") in result

    def test_bmw_m4_g82(self) -> None:
        result = infer_car_generations(
            "FI Exhaust - BMW M4 G82 Valvetronic Catback Exhaust",
            "BMW G82 M4 Fi Exhaust.",
        )
        assert ("BMW", "M4", "G82/G83") in result

    def test_g82_phrase(self) -> None:
        result = infer_car_generations("Vorsteiner BMW G8X M3 | M4 Gloss Black Front Grille", "G82 M4.")
        assert ("BMW", "M4", "G82/G83") in result

    def test_empty_input(self) -> None:
        assert infer_car_generations("", "") == []
        assert infer_car_generations(None, None) == []
        assert infer_car_generations("  ", None) == []

    def test_no_match_returns_empty(self) -> None:
        result = infer_car_generations("Random Universal Part XYZ", "Fits many cars.")
        assert result == []

    def test_product_url_included_in_match(self) -> None:
        # URL might contain car hints in some retailers
        result = infer_car_generations(
            "Exhaust System",
            "High performance exhaust.",
            product_url="https://example.com/supra-a90-exhaust",
        )
        assert ("Toyota", "Supra", "A90") in result

    def test_word_boundary_short_code(self) -> None:
        # "A90" should not match inside unrelated tokens (e.g. "BA90" or "A901")
        result = infer_car_generations("Some Part BA90", "Description.")
        assert ("Toyota", "Supra", "A90") not in result
        result2 = infer_car_generations("Some Part A90 Supra", "Description.")
        assert ("Toyota", "Supra", "A90") in result2

    def test_civic_10th_gen(self) -> None:
        result = infer_car_generations("Honda Civic 10th Gen Cold Air Intake", None)
        assert ("Honda", "Civic", "10th Gen") in result

    def test_fk8_civic_type_r(self) -> None:
        result = infer_car_generations("FK8 Civic Type R Front Lip", "FK8 Type R.")
        assert ("Honda", "Civic Type R", "FK8") in result

    def test_gr_supra_no_subaru_wrx_gr(self) -> None:
        """GR in 'GR Supra' should not match Subaru WRX GR."""
        result = infer_car_generations("Cusco Rear Chassis Power Brace MKV Supra GR A90", None)
        assert ("Toyota", "Supra", "A90") in result
        assert ("Subaru", "WRX", "GR") not in result

    def test_supra_b5_product_no_audi_b5(self) -> None:
        """B5 in product name/variant (e.g. HKS BOV B5) should not match Audi B5."""
        result = infer_car_generations("HKS - Super SQV4 BOV Kit MKV Toyota Supra 3.0 B5", None)
        assert ("Toyota", "Supra", "A90") in result
        assert ("Audi", "A4", "B5") not in result
        assert ("Audi", "S4", "B5") not in result

    def test_mkv_supra_no_vw_mk5(self) -> None:
        """MKV Supra should not match VW Golf/Jetta Mk5."""
        result = infer_car_generations("KW Clubsport Coilover Kit - MKV Supra A90 / A91", None)
        assert ("Toyota", "Supra", "A90") in result
        assert ("Volkswagen", "Golf", "Mk5") not in result

    def test_m340i_m440i_b58(self) -> None:
        """B58 chargepipe for M340i/M440i/Supra."""
        result = infer_car_generations(
            "Active Autowerke B58 Chargepipe BMW M340 I M440I / A90 Supra",
            "B58 G-body charge pipe.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("BMW", "M340i", "G20/G21") in result
        assert ("BMW", "M440i", "G22/G23/G26") in result

    def test_z4_g29_b58(self) -> None:
        """Wagner radiator for Supra GR / BMW Z4 G29 B58."""
        result = infer_car_generations(
            "Wagner Tuning Supra GR / BMW Z4 G29 B58 Engine Radiator Kit",
            "BMW Z4 G29 M40i and Toyota Supra MK5 A90 GR B58.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("BMW", "Z4", "G29") in result

    def test_d2_racing_supra_no_audi_s8_d2(self) -> None:
        """D2 in 'D2 Racing' is brand name, not Audi S8 D2."""
        result = infer_car_generations(
            "D2 Racing RS Series Coilover Kit, MKV Supra",
            "RS Series coilover for Toyota Supra A90.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("Audi", "S8", "D2") not in result

    def test_8s_quarter_mile_no_audi_tt_8s(self) -> None:
        """'8s' (quarter-mile time) in description should not match Audi TT 8S."""
        result = infer_car_generations(
            "CSF 2020+ MKV Supra DCT Transmission Oil Cooler",
            "Installed in the world's fastest A90 Supra – first and only Supra to reach the 8s in the 1/4 mile.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("Audi", "TT", "8S") not in result
        assert ("Audi", "TT RS", "8S") not in result

    def test_g8x_m3_m4_grille(self) -> None:
        """G8X M3 | M4 in product title should match both BMW M3 G80 and M4 G82/G83."""
        result = infer_car_generations(
            "Vorsteiner BMW G8X M3 | M4 Gloss Black Front Motorsport Grille",
            "Compatible with G80 M3 and G82 M4.",
        )
        assert ("BMW", "M3", "G80") in result
        assert ("BMW", "M4", "G82/G83") in result

    def test_ebc_brake_pads_042_mu_no_audi_r8_42(self) -> None:
        """0.42 Mu (friction) and R90 in brake pad text should not match Audi R8 type 42."""
        result = infer_car_generations(
            "EBC - MKV A90 Supra 2.0 Bluestuff Brake Pads",
            "Bluestuff B with a lower 0.42 Mu. R90-approved for street driving.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("Audi", "R8", "Mk1") not in result

    def test_bilstein_b4_supra_z4_no_audi_rs2_b4(self) -> None:
        """Bilstein B4 OE product name should not match Audi RS2 Avant B4."""
        result = infer_car_generations(
            "Bilstein B4 OE A90 Supra / Z4 Rear Suspension Strut",
            "Direct OE replacements for MKV A90 Toyota GR Supra and BMW Z4 M40.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("Audi", "RS2 Avant", "1st Gen") not in result

    def test_bilstein_evo_supra_no_huracan_evo(self) -> None:
        """Bilstein EVO T1 product name should not match Lamborghini Huracán EVO."""
        result = infer_car_generations(
            "Bilstein - EVO T1 Coilover Suspension Kit A90 Supra BMW Z4 M40",
            "Bilstein EVO T1 for MKV A90 Toyota GR Supra / BMW Z4 M40i.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("Lamborghini", "Huracán", "EVO") not in result

    def test_adro_at_p1_supra_wing_no_mclaren_p1(self) -> None:
        """ADRO AT-P1 product code should not match McLaren P1."""
        result = infer_car_generations(
            "ADRO - TOYOTA GR SUPRA AT-P1 REVERSE SWAN NECK WING",
            "AT-P1 Reverse Swan Neck Wing for MKV A90 Toyota GR Supra.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("McLaren", "P1", "1st Gen") not in result

    def test_rexpeed_v10_supra_no_camry_v10(self) -> None:
        """Rexpeed V10 product name (Supra side skirts) should not match Toyota Camry V10."""
        result = infer_car_generations(
            "Rexpeed V10 Carbon Fiber Side Skirts, MKV Supra GR A90 / A91",
            "Side skirt extensions for 2020+ Supra.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("Toyota", "Camry", "1st Gen") not in result

    def test_jdc_lug_bolts_ft_lb_no_charger_lb(self) -> None:
        """Lug bolts description with ft-lb torque should not match Dodge Charger LB."""
        result = infer_car_generations(
            "JDC Titanium Locking Lug Bolts (BMW/A90 Supra)",
            "Torque 140 Nm / 101 ft-lb. Fits 20+ Supra GR, 21 BMW M4 (G82), M3 (G80).",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("BMW", "M3", "G80") in result
        assert ("Dodge", "Charger", "2024+") not in result

    def test_audi_r8_42_still_matches_when_clear(self) -> None:
        """Audi R8 type 42 should still match when text clearly refers to the car."""
        result = infer_car_generations(
            "Exhaust System Audi R8 type 42",
            "For Audi R8 42 2007-2015.",
        )
        assert ("Audi", "R8", "Mk1") in result

    def test_dodge_charger_lb_still_matches_when_clear(self) -> None:
        """Dodge Charger LB should still match when text clearly refers to the car (no ft-lb)."""
        result = infer_car_generations(
            "Body Kit Dodge Charger LB 2024",
            "Widebody for Dodge Charger LB 2024+.",
        )
        assert ("Dodge", "Charger", "2024+") in result

    def test_ctek_battery_charger_na_no_miata_na(self) -> None:
        """CTEK MXS 5.0 NA battery charger product model 'NA' should not match Mazda Miata NA."""
        result = infer_car_generations(
            "CTEK - MXS 5.0 NA Battery Charger",
            "Eight-step battery care. 12V automatic charging and maintenance for vehicle and motorcycle batteries.",
        )
        assert ("Mazda", "Miata", "NA") not in result

    def test_2020_supra_aliases_universal_parts(self) -> None:
        """Parts with 'Supra GR 2020+' or '2020 Toyota Supra' should infer Toyota Supra A90."""
        result = infer_car_generations(
            "Rexpeed Supra GR 2020+ V6 Carbon Fiber Front Fender Duct Panel",
            "For 2020+ Supra. Carbon front fender pieces.",
        )
        assert ("Toyota", "Supra", "A90") in result
        result2 = infer_car_generations(
            "aFe Control Front Sway Bar 2020 Toyota Supra 3.0L",
            "aFe CONTROL sway bars for the Supra. 3-way adjustment.",
        )
        assert ("Toyota", "Supra", "A90") in result2

    def test_jdc_gr_badge_gr_supra_gr_86_gr_corolla(self) -> None:
        """JDC GR Badge (GR Supra/GR 86/GR Corolla) should infer all three Toyota GR cars."""
        result = infer_car_generations(
            'JDC Titanium "GR" Badge (GR Supra/GR 86/GR Corolla)',
            "Applications: GR Supra, GR 86, GR Corolla.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("Toyota", "86", "ZN8") in result
        assert ("Toyota", "GR Corolla", "1st Gen") in result

    def test_deatschwerks_m2_m3_m4_g8x_s58(self) -> None:
        """DeatschWerks G8X S58 kit (M2, M3, M4) should infer M2 G87, M3 G80, M4 G82/G83."""
        result = infer_car_generations(
            "DeatschWerks X3 Series Dual Fuel Pump & PTFE Plumbing Kit",
            "2020+ A90 Toyota Supra B58 / 2021+ BMW M2, M3, M4 G8X S58.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("BMW", "M2", "G87") in result
        assert ("BMW", "M3", "G80") in result
        assert ("BMW", "M4", "G82/G83") in result

    def test_burger_b58_cai_m240i(self) -> None:
        """Burger B58 CAI (M340i, M440i, M240i) should infer M240i G42."""
        result = infer_car_generations(
            "Burger Motorsports BMS B58 BMW Competition Cold Air Intake",
            "2019-2024 BMW M340i, 2022-2024 M440i, and 2022+ M240i including xDrive.",
        )
        assert ("BMW", "M340i", "G20/G21") in result
        assert ("BMW", "M440i", "G22/G23/G26") in result
        assert ("BMW", "M240i", "G42") in result

    def test_burger_strut_braces_g20_g21_g22_g23(self) -> None:
        """Burger strut braces (BMW G20 G21 G22 G23 G26 G42) should infer 3 Series and 4 Series."""
        result = infer_car_generations(
            "BMS Billet Strut Cross Braces - BMW (all engines)",
            "For BMW (G20 G21 G22 G23 G26 G42). Billet aluminum.",
        )
        assert ("BMW", "3 Series", "G20/G21") in result
        assert ("BMW", "4 Series", "G22/G23/G26") in result

    def test_gr_86_no_subaru_wrx_gr(self) -> None:
        """'GR 86' should infer Toyota 86 ZN8, not Subaru WRX GR."""
        result = infer_car_generations(
            "HKS Cold Air Intake Full Kit, GR 86 ZN8 BRZ ZD8",
            "For Toyota GR 86 and Subaru BRZ.",
        )
        assert ("Toyota", "86", "ZN8") in result
        assert ("Subaru", "WRX", "GR") not in result

    def test_csf_bmw_m3_m4_s58_g8x(self) -> None:
        """CSF BMW M3/M4 S58 (G8X) Charge-Air Cooler should infer M3 G80 and M4 G82/G83."""
        result = infer_car_generations(
            "CSF - BMW M3/M4 S58 (G8X) Charge-Air Cooler Manifold",
            "CSF manifold for BMW M3/M4 S58 G8X platform.",
        )
        assert ("BMW", "M3", "G80") in result
        assert ("BMW", "M4", "G82/G83") in result

    def test_oracle_20_21_supra_gr(self) -> None:
        """Oracle 20-21 Supra GR / Toyota Supra GR should infer Toyota Supra A90."""
        result = infer_car_generations(
            "Oracle 20-21 Supra GR RGB+A Headlight DRL Upgrade Kit",
            "ColorSHIFT RGB+A DRL Upgrade for the 2020-2021 Toyota Supra GR.",
        )
        assert ("Toyota", "Supra", "A90") in result

    def test_afe_20_21_toyota_supra_end_links(self) -> None:
        """aFe Control 20-21 Toyota Supra 3.0L end links should infer Toyota Supra A90."""
        result = infer_car_generations(
            "aFe Control 20-21 Toyota Supra 3.0L Rear Adjustable End Links",
            "Adjustable end links for 20-21 Toyota Supra 3.0L.",
        )
        assert ("Toyota", "Supra", "A90") in result

    def test_afe_takeda_supra_exhaust(self) -> None:
        """aFe Takeda exhaust 'off your Supra' should infer Toyota Supra A90."""
        result = infer_car_generations(
            'aFe Takeda 3-1/2" Cat-Back Single Exit Exhaust',
            "Weight reduction: shaves 26 pounds off your Supra. Direct bolt-on.",
        )
        assert ("Toyota", "Supra", "A90") in result

    def test_nitron_toyota_gr86_brz(self) -> None:
        """Nitron Toyota GR86 - BRZ/GR86 should infer Toyota 86 ZN8 and Subaru BRZ ZD8."""
        result = infer_car_generations(
            "Nitron R3 System Coilover - Toyota GR86 - BRZ/GR86",
            "For Toyota GR86 and Subaru BRZ/GR86.",
        )
        assert ("Toyota", "86", "ZN8") in result
        assert ("Subaru", "BRZ", "ZD8") in result

    def test_burger_gen_2_b58_bmw_catch_can(self) -> None:
        """Burger G Chassis Gen 2 B58 BMW catch can should infer BMW M340i G20/G21."""
        result = infer_car_generations(
            "Burger Motorsports - BMS Oil Catch Can for G Chassis Gen 2 2019+ B58 BMW",
            "Designed for Gen 2 B58 BMW application.",
        )
        assert ("BMW", "M340i", "G20/G21") in result

    def test_deatschwerks_supra_m3_m4_g8x(self) -> None:
        """DeatschWerks X3 Series Supra G8X (2020+ Supra, 2021+ BMW M3/M4) should infer all three."""
        result = infer_car_generations(
            "DeatschWerks X3 Series Triple Fuel Pump w/ PTFE Plumbing Supra G8X",
            "2020+ Toyota Supra and 2021+ BMW M3/M4. S58 and B58.",
        )
        assert ("Toyota", "Supra", "A90") in result
        assert ("BMW", "M3", "G80") in result
        assert ("BMW", "M4", "G82/G83") in result

    def test_e46_m3_only_m3_not_330i_or_3_series(self) -> None:
        """E46 is ambiguous standalone; 'E46 M3' should match only BMW M3 E46, not 330i or 3 Series."""
        result = infer_car_generations(
            "E46 M3 VF570 Supercharger System",
            "Machined from 6061-T6 aircraft grade aluminum... E46 M3 throttle bodies.",
        )
        assert ("BMW", "M3", "E46") in result
        assert ("BMW", "330i", "E46") not in result
        assert ("BMW", "3 Series", "E46") not in result
        assert len(result) == 1

    def test_e46_m3_e36_m3_only_two_chassis(self) -> None:
        """Part for E46 M3 and E36 M3 should infer only M3 E46 and M3 E36, not 6 cars (no 330i/3 Series)."""
        result = infer_car_generations(
            "Rogue Engineering Adjustable Rear Control Arm - BMW E46 M3, E36 M3",
            "ARCA for rear camber. E46 M3 and E36 M3.",
        )
        assert ("BMW", "M3", "E46") in result
        assert ("BMW", "M3", "E36") in result
        assert len(result) == 2
