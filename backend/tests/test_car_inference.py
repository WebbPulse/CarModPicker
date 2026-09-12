"""Tests for car make/model/generation inference from part name and description."""

from app.core.car_inference import infer_car_generations


class TestInferCarGenerations:
    """Test infer_car_generations returns expected (make, model, generation_name) triples."""

    def test_mkv_supra_a90(self) -> None:
        """MKV Supra in the name and description resolves to the A90."""
        result = infer_car_generations(
            "Cusco Rear Chassis Power Brace MKV Supra GR A90 / A91",
            "Cusco Rear Chassis Power Brace for the 2020 GR Supra A90.",
        )
        assert ("Toyota", "Supra", "A90") in result

    def test_supra_gr_a90_from_name(self) -> None:
        """Supra GR A90 resolves from the name alone."""
        result = infer_car_generations("Remark Toyota Supra GR A90 Full Titanium Cat-Back Exhaust", None)
        assert ("Toyota", "Supra", "A90") in result

    def test_a90_a91_phrase(self) -> None:
        """The A90 / A91 phrase resolves to the A90."""
        result = infer_car_generations("KW 2 Way Clubsport Coilover Kit - MKV Supra A90 / A91", None)
        assert ("Toyota", "Supra", "A90") in result

    def test_bmw_m4_g82(self) -> None:
        """BMW M4 G82 resolves to the G82/G83 generation."""
        result = infer_car_generations(
            "FI Exhaust - BMW M4 G82 Valvetronic Catback Exhaust",
            "BMW G82 M4 Fi Exhaust.",
        )
        assert ("BMW", "M4", "G82/G83") in result

    def test_g82_phrase(self) -> None:
        """A G82 mention in the description resolves the M4 generation."""
        result = infer_car_generations("Vorsteiner BMW G8X M3 | M4 Gloss Black Front Grille", "G82 M4.")
        assert ("BMW", "M4", "G82/G83") in result

    def test_empty_input(self) -> None:
        """Empty, None and whitespace input yield no triples."""
        assert infer_car_generations("", "") == []
        assert infer_car_generations(None, None) == []
        assert infer_car_generations("  ", None) == []

    def test_no_match_returns_empty(self) -> None:
        """Text with no recognisable car yields no triples."""
        result = infer_car_generations("Random Universal Part XYZ", "Fits many cars.")
        assert result == []

    def test_product_url_included_in_match(self) -> None:
        """The product url is searched alongside the name and description."""
        result = infer_car_generations(
            "Exhaust System",
            "High performance exhaust.",
            product_url="https://example.com/supra-a90-exhaust",
        )
        assert ("Toyota", "Supra", "A90") in result

    def test_word_boundary_short_code(self) -> None:
        """A short chassis code only matches on a word boundary."""
        result = infer_car_generations("Some Part BA90", "Description.")
        assert ("Toyota", "Supra", "A90") not in result
        result2 = infer_car_generations("Some Part A90 Supra", "Description.")
        assert ("Toyota", "Supra", "A90") in result2

    def test_civic_10th_gen(self) -> None:
        """A spelled out generation name resolves the Civic."""
        result = infer_car_generations("Honda Civic 10th Gen Cold Air Intake", None)
        assert ("Honda", "Civic", "10th Gen") in result

    def test_fk8_civic_type_r(self) -> None:
        """FK8 resolves to the Civic Type R rather than the base Civic."""
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
        """Mk4 Supra maps to the A80 engineering code."""
        result = infer_car_generations("Mk4 Supra Downpipe", "For the Mk4 Supra 2JZ.")
        assert ("Toyota", "Supra", "A80") in result

    def test_mkiv_supra_maps_to_a80(self) -> None:
        """MKIV Supra maps to the A80 engineering code."""
        result = infer_car_generations("MKIV Supra Intercooler", None)
        assert ("Toyota", "Supra", "A80") in result

    def test_a80_supra_still_works(self) -> None:
        """The engineering code itself still resolves."""
        result = infer_car_generations("HKS Exhaust A80 Supra", None)
        assert ("Toyota", "Supra", "A80") in result

    def test_mk1_miata_maps_to_na(self) -> None:
        """Mk1 Miata maps to NA."""
        result = infer_car_generations("Mk1 Miata Rollbar", "Mk1 Miata owners.")
        assert ("Mazda", "Miata", "NA") in result

    def test_mk2_miata_maps_to_nb(self) -> None:
        """Mk2 Miata maps to NB."""
        result = infer_car_generations("Mk2 Miata Coilovers", None)
        assert ("Mazda", "Miata", "NB") in result

    def test_mk3_miata_maps_to_nc(self) -> None:
        """Mk3 Miata maps to NC."""
        result = infer_car_generations("Mk3 Miata Header", None)
        assert ("Mazda", "Miata", "NC") in result

    def test_mk4_miata_maps_to_nd(self) -> None:
        """Mk4 Miata maps to ND."""
        result = infer_car_generations("Mk4 Miata Roll Cage", None)
        assert ("Mazda", "Miata", "ND") in result

    def test_mk4_miata_does_not_match_supra(self) -> None:
        """Mk4 next to Miata does not pull in the Mk4 Supra."""
        result = infer_car_generations("Mk4 Miata ND Exhaust", None)
        assert ("Toyota", "Supra", "A80") not in result

    def test_1st_gen_rx7_maps_to_sa_fb(self) -> None:
        """1st Gen RX-7 maps to SA/FB."""
        result = infer_car_generations("1st Gen RX-7 Fuel Pump", None)
        assert ("Mazda", "RX-7", "SA/FB") in result

    def test_2nd_gen_rx7_maps_to_fc(self) -> None:
        """2nd Gen RX-7 maps to FC."""
        result = infer_car_generations("2nd Gen RX-7 Spoiler", None)
        assert ("Mazda", "RX-7", "FC") in result

    def test_3rd_gen_rx7_maps_to_fd(self) -> None:
        """3rd Gen RX-7 maps to FD."""
        result = infer_car_generations("3rd Gen RX-7 Twin Turbo Manifold", None)
        assert ("Mazda", "RX-7", "FD") in result


class TestAdroFalsePositiveFixes:
    """Regression tests for chassis-code collisions seen in the adro.com crawl."""

    def test_corvette_c8_does_not_match_audi_c8(self) -> None:
        """C8 next to Corvette does not pull in the Audi models sharing the code."""
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
        """An explicit Audi RS6 C8 still resolves."""
        result = infer_car_generations("Milltek Audi RS6 C8 Cat-Back Exhaust", None)
        assert ("Audi", "RS6 Avant", "C8") in result

    def test_supra_description_with_970_percent_no_panamera(self) -> None:
        """A percentage in the description does not read as the Panamera 970 code."""
        description = (
            "Transform your GR Supra with the ADRO Facelift kit. "
            "ADRO delivers a huge 970% increase in downforce for a minimal 10% increase in drag."
        )
        result = infer_car_generations("TOYOTA GR SUPRA FRONT BUMPER", description)
        assert ("Toyota", "Supra", "A90") in result
        assert ("Porsche", "Panamera", "970") not in result

    def test_panamera_970_still_matches_when_explicit(self) -> None:
        """An explicit Panamera 970 still resolves."""
        result = infer_car_generations("Panamera 970 Cat-Back Exhaust", None)
        assert ("Porsche", "Panamera", "970") in result

    def test_bmw_g60_no_vw_corrado(self) -> None:
        """G60 next to BMW does not pull in the Corrado sharing the code."""
        result = infer_car_generations("BMW G60 5-SERIES CARBON FIBER FRONT LIP", None)
        assert ("Volkswagen", "Corrado", "G60") not in result
        assert ("BMW", "i5 M60", "G60") in result

    def test_corrado_g60_still_matches_when_explicit(self) -> None:
        """An explicit Corrado G60 still resolves."""
        result = infer_car_generations("Neuspeed VW Corrado G60 Exhaust", None)
        assert ("Volkswagen", "Corrado", "G60") in result


class TestExpandedAliases:
    """Aliases added after ADRO audit found universal-flagged products that should have had cars."""

    def test_f8x_m3_m4_matches_both_bmw_models(self) -> None:
        """The F8X umbrella code resolves to both the M3 and the M4."""
        result = infer_car_generations("BMW F8X M3/M4 CARBON FIBER AIR DUCTS", None)
        assert ("BMW", "M3", "F80") in result
        assert ("BMW", "M4", "F82/F83") in result

    def test_f97_x3m_matches(self) -> None:
        """F97 resolves to the X3 M."""
        result = infer_car_generations("BMW F97 X3M PREPREG FRONT LIP", None)
        assert ("BMW", "X3 M", "F97") in result

    def test_tesla_model_3_highland(self) -> None:
        """Model 3 Highland resolves to its own generation."""
        result = infer_car_generations("TESLA MODEL 3 HIGHLAND CARBON FIBER FRONT LIP", None)
        assert ("Tesla", "Model 3", "Highland") in result

    def test_tesla_model_y(self) -> None:
        """Model Y resolves to its first generation."""
        result = infer_car_generations("TESLA MODEL Y PREPREG FRONT LIP V1", None)
        assert ("Tesla", "Model Y", "1st Gen") in result

    def test_tesla_model_s_plaid(self) -> None:
        """Model S Plaid resolves to the Plaid generation."""
        result = infer_car_generations("TESLA MODEL S PLAID PREPREG CARBON FIBER FRONT LIP", None)
        assert ("Tesla", "Model S", "Plaid") in result

    def test_kia_stinger(self) -> None:
        """Kia Stinger resolves to the CK generation."""
        result = infer_car_generations("KIA STINGER CARBON FIBER SPOILER V2", None)
        assert ("Kia", "Stinger", "CK") in result

    def test_porsche_718(self) -> None:
        """Porsche 718 resolves to the 982 generation."""
        result = infer_car_generations("PORSCHE 718 PREPREG FRONT LIP", None)
        assert ("Porsche", "718", "982") in result

    def test_porsche_992_gt3(self) -> None:
        """A 992.1 GT3 resolves to the 911 992 generation."""
        result = infer_car_generations("PORSCHE 992.1 GT3 PREPREG LOWER FRONT SPLITTER", None)
        assert ("Porsche", "911", "992") in result

    def test_gr_yaris(self) -> None:
        """A title naming both GR Yaris generations resolves to both."""
        result = infer_car_generations("TOYOTA GR YARIS (GEN 1 & 2) CARBON FIBER SIDE SKIRTS", None)
        assert ("Toyota", "GR Yaris", "1st Gen") in result
        assert ("Toyota", "GR Yaris", "2nd Gen") in result

    def test_gr_yaris_gen_1_only(self) -> None:
        """A bare GR Yaris resolves to the first generation only."""
        result = infer_car_generations("TOYOTA GR YARIS DRY CARBON ROOF", None)
        assert ("Toyota", "GR Yaris", "1st Gen") in result
        assert ("Toyota", "GR Yaris", "2nd Gen") not in result

    def test_gr_yaris_gen_2_only(self) -> None:
        """An explicit second generation GR Yaris resolves to both generations."""
        result = infer_car_generations("2nd Gen GR Yaris carbon spoiler", None)
        assert ("Toyota", "GR Yaris", "1st Gen") in result
        assert ("Toyota", "GR Yaris", "2nd Gen") in result

    def test_g90_m5(self) -> None:
        """G90 resolves to the M5 G90/G99 generation."""
        result = infer_car_generations("BMW G90 M5 PREPREG FRONT LIP", None)
        assert ("BMW", "M5", "G90/G99") in result

    def test_x5m_x6m_xm(self) -> None:
        """A shared fitment title resolves each of the three BMW models named."""
        result = infer_car_generations("CSF BMW X5M / X6M / XM HIGH-PERFORMANCE CHARGE-AIR-COOLERS", None)
        assert ("BMW", "X5 M", "F95") in result
        assert ("BMW", "X6 M", "F96") in result
        assert ("BMW", "XM", "F95") in result


class TestM004S02AliasBaseline:
    """A floor on the CAR_ALIASES length, so a deletion that drops recall fails loudly.
    Additive growth is allowed and pinned by the per slice baseline classes.
    """

    EXPECTED_BASELINE: int = 2015

    def test_car_aliases_length_matches_post_s02_baseline(self) -> None:
        """CAR_ALIASES never drops below the recorded floor."""
        from app.core.car_inference import CAR_ALIASES

        assert len(CAR_ALIASES) >= self.EXPECTED_BASELINE, (
            f"CAR_ALIASES length dropped below M004/S02 floor "
            f"({self.EXPECTED_BASELINE} -> {len(CAR_ALIASES)}). Forward-additive growth "
            f"is allowed (per-slice TestM004S0XAliasBaseline classes pin the strict "
            f"equality), but the post-S02 floor must hold — verify a deletion is not "
            f"removing a corpus-vote-derived alias."
        )

    def test_s02_slice_is_declared_in_the_corpus_additions_registry(self) -> None:
        """The S02 slice stays addressable, because the milestone audit locates it by key.

        S02's outcome was a zero-state: the slice derived no alias. The empty
        list records that, where the marker comment it replaces recorded it only
        by sitting in the source text.
        """
        from app.core.car_inference import CORPUS_DERIVED_ADDITIONS

        assert "M004/S02" in CORPUS_DERIVED_ADDITIONS, (
            "M004/S02 missing from CORPUS_DERIVED_ADDITIONS. The milestone audit "
            "locates a slice's additions by this key."
        )
        assert CORPUS_DERIVED_ADDITIONS["M004/S02"] == []


class TestM004S04AliasBaseline:
    """Strict equality on the CAR_ALIASES length for the S04 slice, so any further
    addition or deletion has to bump the baseline in the same change.
    """

    EXPECTED_BASELINE: int = 2015

    def test_car_aliases_length_matches_post_s04_baseline(self) -> None:
        """CAR_ALIASES matches the S04 baseline length exactly."""
        from app.core.car_inference import CAR_ALIASES

        assert len(CAR_ALIASES) == self.EXPECTED_BASELINE, (
            f"CAR_ALIASES length drifted from M004/S04 baseline "
            f"({self.EXPECTED_BASELINE} -> {len(CAR_ALIASES)}). If this is an intentional "
            f"addition, bump EXPECTED_BASELINE in the same commit. If it is a deletion, "
            f"verify it is not removing a corpus-vote-derived alias."
        )

    def test_s04_additions_are_declared_and_merged_into_the_aliases(self) -> None:
        """The S04 slice is addressable by key and its aliases reach CAR_ALIASES.

        Both halves matter: the registry is the anchor the milestone audit and
        future S04+ extensions address, and the membership check proves the
        registry is wired into the table inference actually reads.
        """
        from app.core.car_inference import CAR_ALIASES, CORPUS_DERIVED_ADDITIONS

        additions = CORPUS_DERIVED_ADDITIONS["M004/S04"]
        assert additions, "M004/S04 derived two FL5 aliases; the registry records none"
        for entry in additions:
            assert entry in CAR_ALIASES, f"{entry[0]} is declared for S04 but never reaches CAR_ALIASES"

    def test_dropping_a_declared_addition_would_change_inference(self) -> None:
        """The negative case: the registry is load-bearing, not decorative.

        Inference is re-run over a table with the S04 aliases removed. It must
        stop resolving FL5, which is what proves the passing assertions above
        are carried by the registry rather than by a duplicate alias elsewhere.
        """
        from app.core import car_inference
        from app.core.car_inference import CAR_ALIASES, CORPUS_DERIVED_ADDITIONS

        dropped = set(CORPUS_DERIVED_ADDITIONS["M004/S04"])
        without = [entry for entry in CAR_ALIASES if entry not in dropped]
        assert len(without) == len(CAR_ALIASES) - len(dropped)

        original = car_inference.CAR_ALIASES
        try:
            car_inference.CAR_ALIASES = without
            result = infer_car_generations("Skunk2 Mega Power Header — 2023+ Honda Civic Type R", None)
        finally:
            car_inference.CAR_ALIASES = original

        assert ("Honda", "Civic Type R", "FL5") not in result, (
            "FL5 still resolves with the S04 aliases removed, so the tests above "
            "do not actually prove the registry reaches inference"
        )

    def test_fl5_year_range_aliases_resolve_to_civic_type_r(self) -> None:
        """The two S04-added FL5 year-range aliases must produce the FL5 triple."""
        result = infer_car_generations("Skunk2 Mega Power Header — 2023+ Honda Civic Type R", None)
        assert ("Honda", "Civic Type R", "FL5") in result

        result = infer_car_generations("Eibach Pro-Kit Lowering Springs 2023+ Civic Type R", None)
        assert ("Honda", "Civic Type R", "FL5") in result


class TestParensAdjacencyLimitation:
    """Parentheses between make and model break the adjacency rule, which is deliberate:
    relaxing adjacency would pair unrelated tokens in long fitment lists.
    """

    def test_parens_between_make_and_model_does_not_match_phrase(self) -> None:
        """A parenthesised insert between make and model does not match the phrase."""
        result = infer_car_generations("Brand-New Catback — Nissan (ONLY) GT-R Variant", None)
        assert not any(make == "Nissan" and model == "GT-R" for make, model, _ in result)


class TestTrimMultiGenAliases:
    """A trim spanning several generations emits one alias per generation; adapters layer
    year range narrowing on top to pick the right one.
    """

    def test_gt500_resolves_to_both_5th_and_6th_gen(self) -> None:
        """GT500 resolves to both Mustang generations that carried it."""
        result = infer_car_generations("Ford Mustang GT500 Strut Bar", None)
        assert ("Ford", "Mustang", "5th Gen") in result
        assert ("Ford", "Mustang", "6th Gen") in result

    def test_shelby_gt500_resolves_to_both_5th_and_6th_gen(self) -> None:
        """Shelby GT500 resolves to both Mustang generations that carried it."""
        result = infer_car_generations("Shelby GT500 Carbon Hood", None)
        assert ("Ford", "Mustang", "5th Gen") in result
        assert ("Ford", "Mustang", "6th Gen") in result

    def test_wrx_sti_still_resolves_to_gd_gr_va(self) -> None:
        """WRX STI resolves to all three generations that carried it."""
        result = infer_car_generations("Subaru WRX STI Cat-Back Exhaust", None)
        assert ("Subaru", "WRX", "GD") in result
        assert ("Subaru", "WRX", "GR") in result
        assert ("Subaru", "WRX", "VA") in result


class TestCarAliasesNoDrift:
    """Every alias must reference a real generation triple, because a drifted entry
    silently returns nothing and the part falls through as universal.
    """

    def test_every_alias_resolves_against_car_generations(self) -> None:
        """Every alias resolves against CAR_GENERATIONS."""
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
        """No alias entry appears twice."""
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
    """Inference narrows triples by the title's year range when the text carries a single
    coherent fitment span, and falls back to unfiltered otherwise.
    """

    def test_year_range_narrows_civic_to_one_gen(self) -> None:
        """A year range in the title narrows the Civic to one generation."""
        result = infer_car_generations("2012-2015 Honda Civic Si RDX Injector Plug N Play Clips", None)
        assert ("Honda", "Civic", "9th Gen") in result
        assert ("Honda", "Civic", "8th Gen") not in result
        assert ("Honda", "Civic", "10th Gen") not in result

    def test_individual_years_merge_into_one_span(self) -> None:
        """Individually listed years merge into one span before narrowing."""
        result = infer_car_generations(
            "Honda Civic Si",
            "Fits 2012, 2013, 2014, 2015 Honda Civic Si.",
        )
        assert ("Honda", "Civic", "9th Gen") in result
        assert ("Honda", "Civic", "8th Gen") not in result
        assert ("Honda", "Civic", "10th Gen") not in result

    def test_adjacent_ranges_merge_into_one_span(self) -> None:
        """Adjacent ranges merge into one span before narrowing."""
        result = infer_car_generations(
            "Subaru WRX Coilover Kit",
            "For 2008-2014 and 2015-2018 Subaru WRX.",
        )
        assert ("Subaru", "WRX", "VA") in result
        assert ("Subaru", "WRX", "GD") not in result

    def test_disjoint_ranges_skip_narrowing(self) -> None:
        """Disjoint ranges mean a multi fitment title, so narrowing is skipped."""
        result = infer_car_generations(
            "Toyota Supra Coilover Kit",
            "Fits 1993-1998 MK4 A80 Supra and 2020-2023 MKV A90 Supra.",
        )
        assert ("Toyota", "Supra", "A80") in result
        assert ("Toyota", "Supra", "A90") in result

    def test_open_ended_year_range_narrows(self) -> None:
        """An open ended year range still narrows."""
        result = infer_car_generations("Honda Civic Si 2017+ intake", None)
        assert ("Honda", "Civic", "9th Gen") not in result
        assert ("Honda", "Civic", "10th Gen") in result

    def test_incidental_year_falls_back_to_unfiltered(self) -> None:
        """A year that narrows away every triple falls back to the unfiltered set."""
        result = infer_car_generations(
            "K20A2 Engine Block since 2002 - For Civic Type R FK8",
            None,
        )
        assert ("Honda", "Civic Type R", "FK8") in result

    def test_no_year_range_returns_full_triples(self) -> None:
        """With no year range every matching generation comes back."""
        result = infer_car_generations("Honda Civic Si Cold Air Intake", None)
        gens = {gen for make, model, gen in result if make == "Honda" and model == "Civic"}
        assert "8th Gen" in gens
        assert "9th Gen" in gens
        assert "10th Gen" in gens

    def test_no_match_with_year_range_still_empty(self) -> None:
        """A year range on a title with no car match still yields nothing."""
        result = infer_car_generations("Random Universal Hardware 2015-2020 Mounting Bracket", None)
        assert result == []


class TestMergeYearRanges:
    """The merge policy in isolation.

    It decides whether a title is one fitment span or several.
    """

    def test_overlapping_ranges_merge(self) -> None:
        """Overlapping ranges merge into one."""
        from app.core.car_inference import _merge_year_ranges

        assert _merge_year_ranges([(2010, 2014), (2012, 2018)]) == [(2010, 2018)]

    def test_adjacent_one_year_gap_merges(self) -> None:
        """A one year gap is treated as adjacent and merges."""
        from app.core.car_inference import _merge_year_ranges

        assert _merge_year_ranges([(2010, 2014), (2015, 2018)]) == [(2010, 2018)]

    def test_two_year_gap_stays_disjoint(self) -> None:
        """A two year gap stays disjoint."""
        from app.core.car_inference import _merge_year_ranges

        assert _merge_year_ranges([(2010, 2014), (2016, 2018)]) == [
            (2010, 2014),
            (2016, 2018),
        ]

    def test_unsorted_input_handled(self) -> None:
        """Unsorted input is sorted before merging."""
        from app.core.car_inference import _merge_year_ranges

        assert _merge_year_ranges([(2015, 2018), (2010, 2014)]) == [(2010, 2018)]

    def test_single_year_ranges_collapse(self) -> None:
        """Consecutive single year ranges collapse into one span."""
        from app.core.car_inference import _merge_year_ranges

        assert _merge_year_ranges([(2012, 2012), (2013, 2013), (2014, 2014)]) == [(2012, 2014)]

    def test_empty_input(self) -> None:
        """No ranges merge to no ranges."""
        from app.core.car_inference import _merge_year_ranges

        assert _merge_year_ranges([]) == []
