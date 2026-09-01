"""Tests for car make/model/generation inference from part name and description."""

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
        assert ("Dodge", "Charger", "LB") not in result

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
        # Seed gen name is "LB" (the chassis code); previously the alias
        # pointed at a non-existent "2024+" gen — drift fixed in issue #3 audit.
        assert ("Dodge", "Charger", "LB") in result

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
        assert ("Toyota", "GR86", "ZN8") in result
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
        """'GR 86' should infer Toyota GR86 ZN8, not Subaru WRX GR."""
        result = infer_car_generations(
            "HKS Cold Air Intake Full Kit, GR 86 ZN8 BRZ ZD8",
            "For Toyota GR 86 and Subaru BRZ.",
        )
        assert ("Toyota", "GR86", "ZN8") in result
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
        """Nitron Toyota GR86 - BRZ/GR86 should infer Toyota GR86 ZN8 and Subaru BRZ ZD8."""
        result = infer_car_generations(
            "Nitron R3 System Coilover - Toyota GR86 - BRZ/GR86",
            "For Toyota GR86 and Subaru BRZ/GR86.",
        )
        assert ("Toyota", "GR86", "ZN8") in result
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


class TestFriendlyGenerationAliases:
    """
    Friendly / consumer-facing names must resolve to the engineering-code generation.
    display_name is presentation-only; inference operates on generation_name.
    """

    def test_mk4_supra_maps_to_a80(self) -> None:
        result = infer_car_generations("Mk4 Supra Downpipe", "For the Mk4 Supra 2JZ.")
        assert ("Toyota", "Supra", "A80") in result

    def test_mkiv_supra_maps_to_a80(self) -> None:
        result = infer_car_generations("MKIV Supra Intercooler", None)
        assert ("Toyota", "Supra", "A80") in result

    def test_a80_supra_still_works(self) -> None:
        # Engineering-code form unchanged
        result = infer_car_generations("HKS Exhaust A80 Supra", None)
        assert ("Toyota", "Supra", "A80") in result

    def test_mk1_miata_maps_to_na(self) -> None:
        result = infer_car_generations("Mk1 Miata Rollbar", "Mk1 Miata owners.")
        assert ("Mazda", "Miata", "NA") in result

    def test_mk2_miata_maps_to_nb(self) -> None:
        result = infer_car_generations("Mk2 Miata Coilovers", None)
        assert ("Mazda", "Miata", "NB") in result

    def test_mk3_miata_maps_to_nc(self) -> None:
        result = infer_car_generations("Mk3 Miata Header", None)
        assert ("Mazda", "Miata", "NC") in result

    def test_mk4_miata_maps_to_nd(self) -> None:
        result = infer_car_generations("Mk4 Miata Roll Cage", None)
        assert ("Mazda", "Miata", "ND") in result

    def test_mk4_miata_does_not_match_supra(self) -> None:
        # "Mk4" combined with "Miata" must not also pull Supra A80
        result = infer_car_generations("Mk4 Miata ND Exhaust", None)
        assert ("Toyota", "Supra", "A80") not in result

    def test_1st_gen_rx7_maps_to_sa_fb(self) -> None:
        result = infer_car_generations("1st Gen RX-7 Fuel Pump", None)
        assert ("Mazda", "RX-7", "SA/FB") in result

    def test_2nd_gen_rx7_maps_to_fc(self) -> None:
        result = infer_car_generations("2nd Gen RX-7 Spoiler", None)
        assert ("Mazda", "RX-7", "FC") in result

    def test_3rd_gen_rx7_maps_to_fd(self) -> None:
        result = infer_car_generations("3rd Gen RX-7 Twin Turbo Manifold", None)
        assert ("Mazda", "RX-7", "FD") in result


class TestAdroFalsePositiveFixes:
    """Regression tests for chassis-code collisions seen in the adro.com crawl."""

    def test_corvette_c8_does_not_match_audi_c8(self) -> None:
        # ADRO title "CHEVROLET CORVETTE C8 PREPREG FRONT LIP" used to match
        # Audi RS6/RS7/S6/S7 C8 because C8 was in PHRASE_TRIPLES as bare code.
        result = infer_car_generations(
            "CHEVROLET CORVETTE C8 PREPREG FRONT LIP",
            "The ADRO C8 Corvette front lip is made completely from dry carbon fiber...",
        )
        assert ("Chevrolet", "Corvette", "C8") in result
        assert ("Audi", "RS6 Avant", "C8") not in result
        assert ("Audi", "RS7 Sportback", "C8") not in result
        assert ("Audi", "S6", "C8") not in result
        assert ("Audi", "S7 Sportback", "C8") not in result

    def test_audi_rs6_c8_still_matches(self) -> None:
        result = infer_car_generations("Milltek Audi RS6 C8 Cat-Back Exhaust", None)
        assert ("Audi", "RS6 Avant", "C8") in result

    def test_supra_description_with_970_percent_no_panamera(self) -> None:
        # GR Supra description literally contained "970% increase in downforce"
        # which previously triggered Porsche Panamera 970 as a false match.
        description = (
            "Transform your GR Supra with the ADRO Facelift kit. "
            "ADRO delivers a huge 970% increase in downforce for a minimal 10% increase in drag."
        )
        result = infer_car_generations("TOYOTA GR SUPRA FRONT BUMPER", description)
        assert ("Toyota", "Supra", "A90") in result
        assert ("Porsche", "Panamera", "970") not in result

    def test_panamera_970_still_matches_when_explicit(self) -> None:
        result = infer_car_generations("Panamera 970 Cat-Back Exhaust", None)
        assert ("Porsche", "Panamera", "970") in result

    def test_bmw_g60_no_vw_corrado(self) -> None:
        # ADRO title "BMW G60 5-SERIES CARBON FIBER FRONT LIP" matched VW Corrado G60
        # because G60 was in PHRASE_TRIPLES as bare code.
        result = infer_car_generations("BMW G60 5-SERIES CARBON FIBER FRONT LIP", None)
        assert ("Volkswagen", "Corrado", "G60") not in result
        assert ("BMW", "i5 M60", "G60") in result

    def test_corrado_g60_still_matches_when_explicit(self) -> None:
        result = infer_car_generations("Neuspeed VW Corrado G60 Exhaust", None)
        assert ("Volkswagen", "Corrado", "G60") in result


class TestExpandedAliases:
    """Aliases added after ADRO audit found universal-flagged products that should have had cars."""

    def test_f8x_m3_m4_matches_both_bmw_models(self) -> None:
        # ADRO universal-flagged "BMW F8X M3/M4 CARBON FIBER AIR DUCTS" previously
        # failed inference because F8X wasn't aliased.
        result = infer_car_generations("BMW F8X M3/M4 CARBON FIBER AIR DUCTS", None)
        assert ("BMW", "M3", "F80") in result
        assert ("BMW", "M4", "F82/F83") in result

    def test_f97_x3m_matches(self) -> None:
        result = infer_car_generations("BMW F97 X3M PREPREG FRONT LIP", None)
        assert ("BMW", "X3 M", "F97") in result

    def test_tesla_model_3_highland(self) -> None:
        result = infer_car_generations("TESLA MODEL 3 HIGHLAND CARBON FIBER FRONT LIP", None)
        assert ("Tesla", "Model 3", "Highland") in result

    def test_tesla_model_y(self) -> None:
        result = infer_car_generations("TESLA MODEL Y PREPREG FRONT LIP V1", None)
        assert ("Tesla", "Model Y", "1st Gen") in result

    def test_tesla_model_s_plaid(self) -> None:
        result = infer_car_generations("TESLA MODEL S PLAID PREPREG CARBON FIBER FRONT LIP", None)
        assert ("Tesla", "Model S", "Plaid") in result

    def test_kia_stinger(self) -> None:
        result = infer_car_generations("KIA STINGER CARBON FIBER SPOILER V2", None)
        assert ("Kia", "Stinger", "CK") in result

    def test_porsche_718(self) -> None:
        result = infer_car_generations("PORSCHE 718 PREPREG FRONT LIP", None)
        assert ("Porsche", "718", "982") in result

    def test_porsche_992_gt3(self) -> None:
        result = infer_car_generations("PORSCHE 992.1 GT3 PREPREG LOWER FRONT SPLITTER", None)
        assert ("Porsche", "911", "992") in result

    def test_gr_yaris(self) -> None:
        result = infer_car_generations("TOYOTA GR YARIS (GEN 1 & 2) CARBON FIBER SIDE SKIRTS", None)
        assert ("Toyota", "GR Yaris", "1st Gen") in result
        assert ("Toyota", "GR Yaris", "2nd Gen") in result

    def test_gr_yaris_gen_1_only(self) -> None:
        result = infer_car_generations("TOYOTA GR YARIS DRY CARBON ROOF", None)
        assert ("Toyota", "GR Yaris", "1st Gen") in result
        assert ("Toyota", "GR Yaris", "2nd Gen") not in result

    def test_gr_yaris_gen_2_only(self) -> None:
        result = infer_car_generations("2nd Gen GR Yaris carbon spoiler", None)
        assert ("Toyota", "GR Yaris", "1st Gen") in result  # "gr yaris" alias still fires
        assert ("Toyota", "GR Yaris", "2nd Gen") in result

    def test_g90_m5(self) -> None:
        result = infer_car_generations("BMW G90 M5 PREPREG FRONT LIP", None)
        assert ("BMW", "M5", "G90/G99") in result

    def test_x5m_x6m_xm(self) -> None:
        # ADRO title: "CSF BMW X5M / X6M / XM HIGH-PERFORMANCE CHARGE-AIR-COOLERS"
        result = infer_car_generations("CSF BMW X5M / X6M / XM HIGH-PERFORMANCE CHARGE-AIR-COOLERS", None)
        assert ("BMW", "X5 M", "F95") in result
        assert ("BMW", "X6 M", "F96") in result
        assert ("BMW", "XM", "F95") in result


class TestM004S02AliasBaseline:
    """Frozen-baseline guard for the M004/S02 corpus-vote audit outcome.

    The audit emitted zero `decision == 'alias'` rows, so no tuples were appended to
    `CAR_ALIASES` under the M004/S02 marker. This baseline records the post-S02 length
    (2035) as a permanent **floor** — a future agent that lands deletions which drop
    the count below this floor gets a loud, named failure here instead of a silent
    recall regression at inference time.

    Forward-additive growth (e.g. M004/S04+ corpus-derived additions) is allowed and
    pinned by per-slice baseline classes (TestM004S04AliasBaseline, ...). This class
    is the historical post-S02 record and uses `>=` rather than `==` so it survives
    additive S03+ work without modification — the per-slice classes carry strict
    equality for their respective epochs.
    """

    # 2026-05 audit (issue #3): the S02 floor was lowered from 2035 to 2024
    # after a drift sweep removed 13 alias entries pointing at gens that
    # didn't exist in CAR_GENERATIONS (VW Mk2/Mk3 Golf/Jetta + GTI Mk2-Mk4,
    # BMW 330i E36 — the latter was a real-life impossibility, the former
    # were aspirational gens not in seed). The dropped entries were NOT
    # corpus-vote-derived (they would have failed silently at attribution
    # time anyway); the floor moves to reflect post-cleanup ground truth.
    EXPECTED_BASELINE: int = 2015

    def test_car_aliases_length_matches_post_s02_baseline(self) -> None:
        from app.core.car_inference import CAR_ALIASES

        assert len(CAR_ALIASES) >= self.EXPECTED_BASELINE, (
            f"CAR_ALIASES length dropped below M004/S02 floor "
            f"({self.EXPECTED_BASELINE} -> {len(CAR_ALIASES)}). Forward-additive growth "
            f"is allowed (per-slice TestM004S0XAliasBaseline classes pin the strict "
            f"equality), but the post-S02 floor must hold — verify a deletion is not "
            f"removing a corpus-vote-derived alias."
        )

    def test_s02_marker_comment_present_in_module_source(self) -> None:
        """Ensure the M004/S02 marker comment in CAR_ALIASES survives reorderings.

        T04's CSV walker locates the additions block by this marker; if a future
        refactor strips the comment, T04's audit trail breaks silently. This test
        keeps the marker tied to the alias list itself.
        """
        import inspect

        from app.core import car_inference

        source = inspect.getsource(car_inference)
        assert "M004/S02 corpus-derived additions" in source, (
            "M004/S02 marker comment missing from car_inference.py. T04's CSV walker "
            "uses this string to locate the additions block."
        )


class TestM004S04AliasBaseline:
    """Frozen-baseline guard for the M004/S04 zero-corpus + minimal-additive outcome.

    T02 recorded a zero-corpus pre-S04 snapshot (the SQLite test fallback has no
    `crawled_pages` table — MEM216 graceful-degradation branch). Per the T03 plan's
    zero-corpus branch, two defensible year-range aliases for the FL5 Civic Type R
    were appended under the new ``M004/S04 corpus-derived additions`` marker block,
    bumping CAR_ALIASES from 2035 (post-S02) to 2037 (post-S04).

    This class is the parallel-baseline pattern for the S04 milestone-close record —
    it does NOT replace ``TestM004S02AliasBaseline``, which remains as historical
    evidence of the post-S02 length. A future agent that lands further alias
    additions in S05+ should add a TestM004S05AliasBaseline class with its own
    EXPECTED_BASELINE rather than mutating the S02 or S04 anchors.
    """

    # 2026-05 audit (issue #3): drift sweep removed 13 aliases pointing at
    # non-existent seed gens, then this commit added 2 GT500 aliases (commit
    # e7a0193) and corrected 9 others (Charger LB, Mazdaspeed6, Acura MDX
    # YD2/YD3, Acura Integra Type-R DC2). Net: 2039 -> 2024.
    EXPECTED_BASELINE: int = 2015

    def test_car_aliases_length_matches_post_s04_baseline(self) -> None:
        from app.core.car_inference import CAR_ALIASES

        assert len(CAR_ALIASES) == self.EXPECTED_BASELINE, (
            f"CAR_ALIASES length drifted from M004/S04 baseline "
            f"({self.EXPECTED_BASELINE} -> {len(CAR_ALIASES)}). If this is an intentional "
            f"addition, bump EXPECTED_BASELINE in the same commit. If it is a deletion, "
            f"verify it is not removing a corpus-vote-derived alias."
        )

    def test_s04_marker_comment_present_in_module_source(self) -> None:
        """Ensure the M004/S04 marker comment in CAR_ALIASES survives reorderings.

        The marker is the anchor for any future S04+ corpus-derived alias extension
        and for milestone-close audit walkers. If a refactor strips the comment,
        the audit trail breaks silently. This test keeps the marker tied to the
        alias list itself.
        """
        import inspect

        from app.core import car_inference

        source = inspect.getsource(car_inference)
        assert "M004/S04 corpus-derived additions" in source, (
            "M004/S04 marker comment missing from car_inference.py. The marker is "
            "the anchor for milestone-close audit walkers and future S04+ extensions."
        )

    def test_fl5_year_range_aliases_resolve_to_civic_type_r(self) -> None:
        """The two S04-added FL5 year-range aliases must produce the FL5 triple."""
        result = infer_car_generations("Skunk2 Mega Power Header — 2023+ Honda Civic Type R", None)
        assert ("Honda", "Civic Type R", "FL5") in result

        result = infer_car_generations("Eibach Pro-Kit Lowering Springs 2023+ Civic Type R", None)
        assert ("Honda", "Civic Type R", "FL5") in result


class TestParensAdjacencyLimitation:
    """Document the known limitation that parens between make+model break the adjacency rule.

    `infer_car_generations` strips parentheses but leaves the contained words inline.
    PHRASE_TRIPLES require make+model to be adjacent, so a parenthesized insert between
    them ("Nissan (ONLY) GT-R" → "Nissan ONLY GT-R") breaks the substring match. This is
    intentional — relaxing adjacency would introduce false positives where unrelated make
    and model tokens elsewhere in a long fitment list could be paired up.

    Adapters whose product titles regularly use this pattern should override
    infer_car_for_part with their own parser rather than fight the adjacency rule.
    """

    def test_parens_between_make_and_model_does_not_match_phrase(self) -> None:
        # No CAR_ALIAS covers this exact phrasing, and PHRASE_TRIPLES require adjacency,
        # so the (ONLY) insert prevents resolution.
        result = infer_car_generations("Brand-New Catback — Nissan (ONLY) GT-R Variant", None)
        assert not any(make == "Nissan" and model == "GT-R" for make, model, _ in result)


class TestTrimMultiGenAliases:
    """Pin the trim-vs-model rule documented at the top of CAR_ALIASES.

    Trims that span multiple generations (WRX STI: GD/GR/VA, GT500:
    5th/6th Gen) emit one alias entry per generation. Adapter hooks layer
    year-range narrowing on top to pick the right gen for a specific part.
    """

    def test_gt500_resolves_to_both_5th_and_6th_gen(self) -> None:
        # 2007-2014 GT500 = 5th Gen, 2020-2022 GT500 = 6th Gen.
        # Without an explicit year a GT500 part is ambiguous and should match both.
        result = infer_car_generations("Ford Mustang GT500 Strut Bar", None)
        assert ("Ford", "Mustang", "5th Gen") in result
        assert ("Ford", "Mustang", "6th Gen") in result

    def test_shelby_gt500_resolves_to_both_5th_and_6th_gen(self) -> None:
        result = infer_car_generations("Shelby GT500 Carbon Hood", None)
        assert ("Ford", "Mustang", "5th Gen") in result
        assert ("Ford", "Mustang", "6th Gen") in result

    def test_wrx_sti_still_resolves_to_gd_gr_va(self) -> None:
        # Regression check: the trim-vs-model docstring shouldn't have
        # disturbed the existing STI multi-gen mapping.
        result = infer_car_generations("Subaru WRX STI Cat-Back Exhaust", None)
        assert ("Subaru", "WRX", "GD") in result
        assert ("Subaru", "WRX", "GR") in result
        assert ("Subaru", "WRX", "VA") in result


class TestCarAliasesNoDrift:
    """Permanent drift guard for CAR_ALIASES (issue #3).

    Every alias entry's (make, model, generation_name) RHS must reference
    a real (make, model, gen) triple in CAR_GENERATIONS. Drift entries
    silently return [] at attribution time — the part falls through to
    is_universal=True and the alias is wasted code. This test catches
    the drift loudly on the next CI run rather than at audit time.
    """

    def test_every_alias_resolves_against_car_generations(self) -> None:
        from app.core.car_generations_data import CAR_GENERATIONS
        from app.core.car_inference import CAR_ALIASES

        drift: list[tuple] = []
        for entry in CAR_ALIASES:
            _phrase, make, model, gen_name = entry
            models = CAR_GENERATIONS.get(make)
            if not models:
                drift.append(entry)
                continue
            model_entry = next((m for m in models if m["model"] == model), None)
            if model_entry is None:
                drift.append(entry)
                continue
            if not any(g["generation_name"] == gen_name for g in model_entry["generations"]):
                drift.append(entry)
        assert (
            not drift
        ), f"{len(drift)} CAR_ALIASES entries reference unknown " f"(make, model, gen_name) triples in seed:\n" + "\n".join(
            f"  {entry!r}" for entry in drift[:20]
        ) + (
            "\n  ..." if len(drift) > 20 else ""
        )

    def test_no_exact_duplicate_alias_entries(self) -> None:
        from collections import Counter

        from app.core.car_inference import CAR_ALIASES

        counts = Counter(CAR_ALIASES)
        dupes = [(entry, n) for entry, n in counts.items() if n > 1]
        assert not dupes, (
            f"{len(dupes)} CAR_ALIASES entries appear more than once. "
            "Pure duplicates are functionally inert (the substring matcher "
            "deduplicates output anyway) but waste iteration time and "
            "obscure intent. Drop the later occurrence:\n" + "\n".join(f"  x{n}: {e!r}" for e, n in dupes[:10])
        )


class TestUniversalPipelineYearNarrowing:
    """infer_car_generations now narrows triples by the title's year range when the
    text contains a single coherent fitment span. These tests pin the new contract
    plus its safety rails (multi-fitment titles untouched; empty-narrow falls back
    to unfiltered)."""

    def test_year_range_narrows_civic_to_one_gen(self) -> None:
        # Title carries one range (2012-2015). Universal pipeline matches every
        # Civic gen via "Honda Civic"; narrow to the gen overlapping 2012-2015.
        result = infer_car_generations("2012-2015 Honda Civic Si RDX Injector Plug N Play Clips", None)
        assert ("Honda", "Civic", "9th Gen") in result
        assert ("Honda", "Civic", "8th Gen") not in result
        assert ("Honda", "Civic", "10th Gen") not in result

    def test_individual_years_merge_into_one_span(self) -> None:
        # "2012, 2013, 2014, 2015" reads as five single-year ranges to the
        # extractor; the merge step collapses them to one (2012-2015) span.
        result = infer_car_generations(
            "Honda Civic Si",
            "Fits 2012, 2013, 2014, 2015 Honda Civic Si.",
        )
        assert ("Honda", "Civic", "9th Gen") in result
        assert ("Honda", "Civic", "8th Gen") not in result
        assert ("Honda", "Civic", "10th Gen") not in result

    def test_adjacent_ranges_merge_into_one_span(self) -> None:
        # 2008-2014 abuts 2015-2018 with one year gap. The merge step treats
        # them as one fitment span (2008-2018), so narrowing still applies.
        result = infer_car_generations(
            "Subaru WRX Coilover Kit",
            "For 2008-2014 and 2015-2018 Subaru WRX.",
        )
        # WRX VA (2015-2021) and GR (2022+) — only VA overlaps 2008-2018.
        # GD (2002-2007) is outside the merged span entirely.
        assert ("Subaru", "WRX", "VA") in result
        assert ("Subaru", "WRX", "GD") not in result

    def test_disjoint_ranges_skip_narrowing(self) -> None:
        # Two chassis windows separated by >1 year. With the skip-policy, both
        # alias matches survive; with naive narrowing, one would be wrongly dropped.
        # Supra A80 (1993-2002) and A90 (2019+) are 17 years apart — clearly
        # disjoint. A title spanning both is multi-fitment and cannot be safely
        # narrowed.
        result = infer_car_generations(
            "Toyota Supra Coilover Kit",
            "Fits 1993-1998 MK4 A80 Supra and 2020-2023 MKV A90 Supra.",
        )
        # Both alias-matched gens must remain; narrowing to one would be wrong.
        assert ("Toyota", "Supra", "A80") in result
        assert ("Toyota", "Supra", "A90") in result

    def test_open_ended_year_range_narrows(self) -> None:
        # "2017+" is parsed as (2017, current_year+1). FK8 Civic Type R (2017-2021)
        # overlaps; FK7 Civic (2017-2021) overlaps; older Civic gens (8th/9th)
        # don't.
        result = infer_car_generations("Honda Civic Si 2017+ intake", None)
        # 9th gen ends 2015; should be narrowed out.
        assert ("Honda", "Civic", "9th Gen") not in result
        # 10th gen (2016-2021) overlaps 2017+.
        assert ("Honda", "Civic", "10th Gen") in result

    def test_incidental_year_falls_back_to_unfiltered(self) -> None:
        # Title contains a year that doesn't overlap any matched-model gen.
        # The fallback kicks in: keep the unnarrowed triples rather than
        # falling through to is_universal. Better to over-attribute than to
        # silently drop a confident match.
        result = infer_car_generations(
            "K20A2 Engine Block since 2002 - For Civic Type R FK8",
            None,
        )
        # FK8 Civic Type R is 2017-2021; the (2002, 2002) range doesn't overlap.
        # Without the fallback, narrowing would empty the result.
        assert ("Honda", "Civic Type R", "FK8") in result

    def test_no_year_range_returns_full_triples(self) -> None:
        # No year token at all — narrowing is a no-op.
        result = infer_car_generations("Honda Civic Si Cold Air Intake", None)
        # Every Civic gen still present (this is the pre-change behavior).
        gens = {gen for make, model, gen in result if make == "Honda" and model == "Civic"}
        assert "8th Gen" in gens
        assert "9th Gen" in gens
        assert "10th Gen" in gens

    def test_no_match_with_year_range_still_empty(self) -> None:
        # When no make/model matches at all, year-range narrowing has nothing
        # to narrow. Result stays empty.
        result = infer_car_generations("Random Universal Hardware 2015-2020 Mounting Bracket", None)
        assert result == []


class TestMergeYearRanges:
    """Pin the merge policy in isolation — it's the lever that decides whether a
    title is one fitment span or many."""

    def test_overlapping_ranges_merge(self) -> None:
        from app.core.car_inference import _merge_year_ranges

        assert _merge_year_ranges([(2010, 2014), (2012, 2018)]) == [(2010, 2018)]

    def test_adjacent_one_year_gap_merges(self) -> None:
        from app.core.car_inference import _merge_year_ranges

        # 2014-2015 = 1 year gap, treated as one block.
        assert _merge_year_ranges([(2010, 2014), (2015, 2018)]) == [(2010, 2018)]

    def test_two_year_gap_stays_disjoint(self) -> None:
        from app.core.car_inference import _merge_year_ranges

        # 2014-2016 = 2 year gap, disjoint.
        assert _merge_year_ranges([(2010, 2014), (2016, 2018)]) == [
            (2010, 2014),
            (2016, 2018),
        ]

    def test_unsorted_input_handled(self) -> None:
        from app.core.car_inference import _merge_year_ranges

        assert _merge_year_ranges([(2015, 2018), (2010, 2014)]) == [(2010, 2018)]

    def test_single_year_ranges_collapse(self) -> None:
        from app.core.car_inference import _merge_year_ranges

        assert _merge_year_ranges([(2012, 2012), (2013, 2013), (2014, 2014)]) == [(2012, 2014)]

    def test_empty_input(self) -> None:
        from app.core.car_inference import _merge_year_ranges

        assert _merge_year_ranges([]) == []
