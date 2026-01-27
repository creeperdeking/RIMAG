package RIMAEL
  // 1) A simple variable thermal conductor ("heat valve")
  /** Central lumped mass that exchanges heat with:
                        - Ncond conduction/contact sources via FracConduction
                        - Nrad  radiative sources via FracRadiation
                        Each branch i is scaled by a user-supplied fraction f[i](t). */
  /* One external radiative connector feeding a central HeatCapacitor */
  /* One external radiative connector feeding a central HeatCapacitor. */
  /** Radiative exchange whose strength is the visible/view fraction. 
                    Q = f * Gr_base * sigma * (Ta^4 - Tb^4) */
  /* Fraction-scaled radiative path (inherits a decent icon from Element1D). */

  model FracRadiation
    import Modelica.Units.SI;
    extends Modelica.Thermal.HeatTransfer.Interfaces.Element1D;
    parameter Real Gr_base(min = 0) = 1 "Radiation factor (e.g., ε*A or A/(1/ε1+1/ε2-1))";
    Modelica.Blocks.Interfaces.RealInput f "Visible/view fraction 0..1" annotation(
      Placement(transformation(extent = {{-10, 90}, {10, 110}}), iconTransformation(extent = {{-10, 90}, {10, 110}})));
  protected
    Real fclamped;
  equation
    fclamped = max(0, min(1, f));
    Q_flow = fclamped*Gr_base*Modelica.Constants.sigma*(port_a.T^4 - port_b.T^4);
    annotation(
      Icon(coordinateSystem(extent = {{-100, -100}, {100, 100}})),
      Diagram(coordinateSystem(extent = {{-100, -100}, {100, 100}})),
      experiment(StartTime = 0, StopTime = 1, Tolerance = 1e-06, Interval = 0.002));
  end FracRadiation;

  model Reactor
    inner parameter Real Gr_fuel = 1.009;
    inner parameter Real Gr_shield = 0.0;
    inner parameter Real Gr_tpv = 0.156;
    inner parameter Real P0 = 383771 "Original stationary power (W)";
    inner parameter Real tShutdown = 700 "s";
    inner parameter Real eps = 1e-6 "Avoid singularity at tau=0 (hours)";
    replaceable package Medium = Modelica.Media.Air.DryAirNasa;
    inner Real rotRPS_common "rev/s";
    Modelica.Thermal.HeatTransfer.Components.HeatCapacitor FuelPlate(C = 35534, T(start = 1523.15)) annotation(
      Placement(transformation(origin = {0, 46}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sources.FixedTemperature coolWaterTemp(T = 333.15) annotation(
      Placement(transformation(origin = {0, -6}, extent = {{-10, -10}, {10, 10}})));
    Disk disk(heat_capacity_section = 23569, T_start = 1373.15) annotation(
      Placement(transformation(origin = {60, 14}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Sources.PrescribedHeatFlow prescribedHeatFlow annotation(
      Placement(transformation(origin = {-64, 32}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Blocks.Sources.RealExpression Qexpr(y = if time < tShutdown then P0 else 0.0128*P0*(max((time - tShutdown)/3600, eps)^(-0.2) - (7200 + max((time - tShutdown)/3600, eps))^(-0.2))) annotation(
      Placement(transformation(origin = {-102, 32}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Blocks.Sources.RealExpression rotationSpeed(y = if time < tShutdown then 1 else 0) annotation(
      Placement(transformation(origin = {-104, 8}, extent = {{-10, -10}, {10, 10}})));
    GapAtmosphere AtmosphereFuelDisk(tSwitch = tShutdown) annotation(
      Placement(transformation(origin = {82, 76}, extent = {{-10, -10}, {10, 10}})));
    RIMAEL.GapAtmosphere AtmosphereFuelDisk1(tSwitch = tShutdown) annotation(
      Placement(transformation(origin = {-36, 14}, extent = {{10, -10}, {-10, 10}}, rotation = -0)));
  equation
    rotRPS_common = rotationSpeed.y;
    connect(FuelPlate.port, disk.fuel_port1) annotation(
      Line(points = {{0, 32}, {0, 20}, {50, 20}}, color = {191, 0, 0}));
    connect(coolWaterTemp.port, disk.TPV_port1) annotation(
      Line(points = {{10, -6}, {26, -6}, {26, 14}, {50, 14}}, color = {191, 0, 0}));
    connect(coolWaterTemp.port, disk.TPV_port2) annotation(
      Line(points = {{10, -6}, {80, -6}, {80, 14}, {70, 14}}, color = {191, 0, 0}));
    connect(FuelPlate.port, disk.fuel_port2) annotation(
      Line(points = {{0, 32}, {70, 32}, {70, 20}}, color = {191, 0, 0}));
    connect(prescribedHeatFlow.port, FuelPlate.port) annotation(
      Line(points = {{-54, 32}, {0, 32}}, color = {191, 0, 0}));
    connect(Qexpr.y, prescribedHeatFlow.Q_flow) annotation(
      Line(points = {{-91, 32}, {-74, 32}}, color = {0, 0, 127}));
    connect(FuelPlate.port, AtmosphereFuelDisk.port_a) annotation(
      Line(points = {{0, 32}, {36, 32}, {36, 76}, {72, 76}}, color = {191, 0, 0}));
    connect(coolWaterTemp.port, disk.shield1_port1) annotation(
      Line(points = {{10, -6}, {26, -6}, {26, 16}, {50, 16}}, color = {191, 0, 0}));
    connect(coolWaterTemp.port, disk.shield2_port1) annotation(
      Line(points = {{10, -6}, {26, -6}, {26, 10}, {50, 10}}, color = {191, 0, 0}));
    connect(coolWaterTemp.port, disk.shield2_port2) annotation(
      Line(points = {{10, -6}, {80, -6}, {80, 10}, {70, 10}}, color = {191, 0, 0}));
    connect(coolWaterTemp.port, disk.shield1_port2) annotation(
      Line(points = {{10, -6}, {80, -6}, {80, 16}, {70, 16}}, color = {191, 0, 0}));
  connect(AtmosphereFuelDisk1.port_a, FuelPlate.port) annotation(
      Line(points = {{-26, 14}, {0, 14}, {0, 32}}, color = {191, 0, 0}));
    annotation(
      Diagram(coordinateSystem(extent = {{-120, 100}, {180, -60}})),
      experiment(StartTime = 0, StopTime = 1400, Tolerance = 1e-06, Interval = 0.2));
  end Reactor;

  /* --- block: overlap fraction of the MOBILE segment --------------------- */
  /* --- Block: overlap fraction using degrees ------------------------------ */
  /* Fixed arc [ss1a_deg, ss1b_deg], rotating arc [ms1a_deg, ms1b_deg] + θ(t),
           with θ(t) = 360*rotRPS*time (deg). Output is overlap fraction of the
           MOBILE arc (0..1) and percentage (0..100). */

  block CircularSegmentOverlapDeg
    // Parameters (all in degrees)
    parameter Real ss1a_deg = 0 "Static segment start (deg)";
    parameter Real ss1b_deg = 90 "Static segment end   (deg)";
    parameter Real ms1a_deg = 30 "Mobile segment start (deg)";
    parameter Real ms1b_deg = 150 "Mobile segment end   (deg)";
    // Mobile rotation speed (rotations per second; can be negative)
    input Real rotRPS = 0.1 "Mobile rotation speed (rev/s)";
    // Outputs
    Modelica.Blocks.Interfaces.RealOutput frac "Overlap as a fraction of the MOBILE segment length (0..1)" annotation(
      Placement(transformation(extent = {{90, -10}, {110, 10}}), iconTransformation(extent = {{90, -10}, {110, 10}})));
  protected
    constant Real CIRCLE = 360;
    Real theta_deg;
    // accumulated rotation (deg)
    Real msLen_deg;
    // mobile arc length (deg)
    Real msA_deg;
    Real msB_deg;
    // mobile arc bounds at time t
    Real Lovl_deg;
    // overlap length (deg)
  equation
// Time-varying rotation (deg)
    theta_deg = CIRCLE*rotRPS*time;
// Mobile arc at time t
    msA_deg = ms1a_deg + theta_deg;
    msB_deg = ms1b_deg + theta_deg;
// Mobile arc length (constant)
    msLen_deg = mod360(ms1b_deg - ms1a_deg);
// Overlap length and fraction (guard against zero-length mobile arc)
    Lovl_deg = overlapArcLenDeg(ss1a_deg, ss1b_deg, msA_deg, msB_deg);
    frac = if msLen_deg > 0 then max(0, min(1, Lovl_deg/msLen_deg)) else 0;
    annotation(
      Icon(coordinateSystem(extent = {{-100, -100}, {100, 100}}), graphics = {Rectangle(extent = {{-80, 40}, {80, -40}}, lineColor = {0, 0, 0}), Text(extent = {{-78, 60}, {78, 90}}, textString = "Arc Overlap (deg)"), Ellipse(extent = {{-40, 20}, {40, -20}}), Line(points = {{-80, 0}, {80, 0}}), Line(points = {{0, -40}, {0, 40}})}));
  end CircularSegmentOverlapDeg;

  /* --- helpers ------------------------------------------------------------ */
  // Map any angle to [0, 2*pi)

  function mod2pi
    input Real x;
    output Real y;
  protected
    Real twoPi = 2*Modelica.Constants.pi;
  algorithm
    y := x - twoPi*floor(x/twoPi);
  end mod2pi;

  // Overlap length of two closed intervals on the real line: [a,b] and [c,d]
  /* Overlap length of two closed intervals on the real line: [a,b] and [c,d] */

  function overlapInterval
    input Real a;
    input Real b;
    input Real c;
    input Real d;
    output Real L;
  algorithm
    L := max(0.0, min(b, d) - max(a, c));
  end overlapInterval;

  // Overlap arc length (radians) between two circular arcs
  // Arc i is the CCW path from ai to bi on [0, 2*pi), wrap allowed.
  /* Overlap arc length (degrees) between two CCW arcs on a circle.
               Arc i is the CCW path from ai to bi in degrees; wrap allowed. */

  function overlapArcLenDeg
    input Real a1_deg;
    input Real b1_deg;
    input Real a2_deg;
    input Real b2_deg;
    output Real L_deg;
  protected
    constant Real CIRCLE = 360;
    // normalized copies
    Real a1n;
    Real b1n;
    Real a2n;
    Real b2n;
    Real L1;
    // length of arc 1 in [0,360)
    Real A2;
    Real B2;
    // arc 2 expressed in frame where arc1 starts at 0
  algorithm
// Normalize all bounds to [0, 360)
    a1n := mod360(a1_deg);
    b1n := mod360(b1_deg);
    a2n := mod360(a2_deg);
    b2n := mod360(b2_deg);
// Length of arc 1 and rotate frame so arc1 starts at 0
    L1 := mod360(b1n - a1n);
// in [0, 360)
    A2 := mod360(a2n - a1n);
    B2 := mod360(b2n - a1n);
// Now arc1 is [0, L1]; arc2 may wrap. Sum overlaps with non-wrapping parts.
    if B2 >= A2 then
      L_deg := overlapInterval(0.0, L1, A2, B2);
    else
// arc2 wraps across 360 → split into [A2, 360) and [0, B2]
      L_deg := overlapInterval(0.0, L1, A2, CIRCLE) + overlapInterval(0.0, L1, 0.0, B2);
    end if;
// If arc1 has zero length, force no overlap
    if L1 <= 0 then
      L_deg := 0;
    end if;
  end overlapArcLenDeg;

  /* Map any angle (deg) to [0, 360) */

  function mod360
    input Real x_deg;
    output Real y_deg;
  protected
    constant Real CIRCLE = 360;
  algorithm
    y_deg := x_deg - CIRCLE*floor(x_deg/CIRCLE);
  end mod360;

  /* Overlap of two arcs defined by section indices. Wraps and rotates the
         MOBILE arc; output is overlap of the *mobile* arc as a fraction (0..1)
         and percent (0..100). */

  block CircularSegmentOverlapBySections
    // --- Parameters (discrete section interface) ---
    parameter Integer N(min = 1) = 8 "Total number of equal sections on the disc";
    parameter Integer sS1(min = 1) = 1 "Static segment start section index (1..N)";
    parameter Integer Ls1(min = 1) = 2 "Static segment length in sections (0..N)";
    parameter Integer sM(min = 1) = 2 "Mobile segment start section index (1..N)";
    parameter Integer Lm(min = 1) = 3 "Mobile segment length in sections (0..N)";
    input Real rotRPS = 0.10 "Mobile rotation speed (rev/s; can be negative)";
    // --- Outputs ---
    Modelica.Blocks.Interfaces.RealOutput frac "Overlap as a fraction of the MOBILE segment length (0..1)" annotation(
      Placement(transformation(extent = {{90, -10}, {110, 10}}), iconTransformation(extent = {{90, -10}, {110, 10}})));
    // --- Internal parameterization in degrees ---
  protected
    parameter Real delta = 360.0/N "Section width (deg)";
    // Map section indices/lengths to arc bounds in degrees
    parameter Real ss1a_deg = (sS1 - 1)*delta;
    parameter Real ss1b_deg = ss1a_deg + Ls1*delta;
    // Note: If Lm == N (full disk), CircularSegmentOverlapDeg would see a
    // 0-length arc via mod360. We subtract a tiny epsilon to avoid degeneracy.
    parameter Real eps = 1e-9;
    parameter Real ms1a_deg = (sM - 1)*delta;
    parameter Real ms1b_deg = ms1a_deg + (if Lm == N then (Lm*delta - eps) else Lm*delta);
    // Encapsulated degree-based overlap block
    CircularSegmentOverlapDeg ovl(ss1a_deg = ss1a_deg, ss1b_deg = ss1b_deg, ms1a_deg = ms1a_deg, ms1b_deg = ms1b_deg, rotRPS = rotRPS) annotation(
      Placement(transformation(origin = {-16, -8}, extent = {{-36, -18}, {36, 18}})));
  equation
    connect(ovl.frac, frac);
// Basic range checks (evaluated at runtime)
    assert(sS1 >= 1 and sS1 <= N, "sS1 out of range 1..N");
    assert(sM >= 1 and sM <= N, "sM out of range 1..N");
    assert(Ls1 >= 1 and Ls1 <= N, "Ls1 must be 0..N");
    assert(Lm >= 1 and Lm <= N, "Lm must be 0..N");
    annotation(
      Icon(coordinateSystem(extent = {{-100, -100}, {100, 100}}), graphics = {Rectangle(extent = {{-80, 40}, {80, -40}}, lineColor = {0, 0, 0}), Text(extent = {{-78, 60}, {78, 90}}, textString = "Arc Overlap (sections)"), Ellipse(extent = {{-40, 20}, {40, -20}}), Line(points = {{-80, 0}, {80, 0}}), Line(points = {{0, -40}, {0, 40}})}),
      Diagram(coordinateSystem(extent = {{-100, -100}, {100, 100}}), graphics = {Text(extent = {{-98, 84}, {98, 98}}, textString = "Overlap of rotating vs static arc from section indices")}));
  end CircularSegmentOverlapBySections;

  model DiskSection
    import Modelica.Units.SI;
    // Parameters
    parameter SI.HeatCapacity C = 6758 "Heat capacity (J/K)";
    parameter SI.Temperature T_start = 293.15 "Start temperature";
    parameter Integer section_num = 2 "Assigned disk section";
    outer parameter Real rotRPS_common;
    outer parameter Real Gr_fuel;
    outer parameter Real Gr_shield;
    outer parameter Real Gr_tpv;
    // External port (environment side) + fraction input
    // Internals
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a capacitor_port annotation(
      Placement(transformation(origin = {122, -44}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -50}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a fuel_port annotation(
      Placement(transformation(origin = {-120, 80}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 56}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield1_port annotation(
      Placement(transformation(origin = {-120, 24}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 26}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a TPV_port annotation(
      Placement(transformation(origin = {-120, -30}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -4}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield2_port annotation(
      Placement(transformation(origin = {-120, -80}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -36}, extent = {{-10, -10}, {10, 10}})));
    FracRadiation fracRad_fuel(Gr_base = Gr_fuel) annotation(
      Placement(transformation(origin = {-22, 80}, extent = {{-16, -16}, {16, 16}})));
    FracRadiation fracRad_shield1(Gr_base = Gr_shield) annotation(
      Placement(transformation(origin = {-22, 24}, extent = {{-16, -16}, {16, 16}})));
    FracRadiation fracRad_shield2(Gr_base = Gr_shield) annotation(
      Placement(transformation(origin = {-22, -80}, extent = {{-16, -16}, {16, 16}})));
    FracRadiation fracRad_TPV(Gr_base = Gr_tpv) annotation(
      Placement(transformation(origin = {-22, -30}, extent = {{-16, -16}, {16, 16}})));
    CircularSegmentOverlapBySections circularSegmentOverlapBySections_shield2(sM = section_num, N = 12, sS1 = 12, Ls1 = 2, Lm = 2, rotRPS = rotRPS_common) annotation(
      Placement(transformation(origin = {-63, -55}, extent = {{-15, -15}, {15, 15}})));
    CircularSegmentOverlapBySections circularSegmentOverlapBySections_TPV(sM = section_num, N = 12, sS1 = 6, Ls1 = 6, Lm = 2, rotRPS = rotRPS_common) annotation(
      Placement(transformation(origin = {-63, -5}, extent = {{-15, -15}, {15, 15}})));
    CircularSegmentOverlapBySections circularSegmentOverlapBySections_fuel(N = 12, Ls1 = 2, sM = section_num, Lm = 2, sS1 = 2, rotRPS = rotRPS_common) annotation(
      Placement(transformation(origin = {-63, 107}, extent = {{-15, -15}, {15, 15}})));
    CircularSegmentOverlapBySections circularSegmentOverlapBySections_shield1(sM = section_num, N = 12, sS1 = 4, Ls1 = 2, Lm = 2, rotRPS = rotRPS_common) annotation(
      Placement(transformation(origin = {-63, 51}, extent = {{-15, -15}, {15, 15}})));
    Modelica.Thermal.HeatTransfer.Components.HeatCapacitor disk_section_heatCapacitor(C = C, T(start = T_start)) annotation(
      Placement(transformation(origin = {73, 15}, extent = {{-25, -25}, {25, 25}})));
  equation
// EXACTLY ONE thermal path: p --(port_a)-> rad --(port_b)-> cap
    connect(circularSegmentOverlapBySections_shield2.frac, fracRad_shield2.f) annotation(
      Line(points = {{-48, -54}, {-22, -54}, {-22, -64}}, color = {0, 0, 127}));
    connect(circularSegmentOverlapBySections_TPV.frac, fracRad_TPV.f) annotation(
      Line(points = {{-48, -4}, {-22, -4}, {-22, -14}}, color = {0, 0, 127}));
    connect(circularSegmentOverlapBySections_shield1.frac, fracRad_shield1.f) annotation(
      Line(points = {{-48, 52}, {-22, 52}, {-22, 40}}, color = {0, 0, 127}));
    connect(circularSegmentOverlapBySections_fuel.frac, fracRad_fuel.f) annotation(
      Line(points = {{-48, 108}, {-22, 108}, {-22, 96}}, color = {0, 0, 127}));
    connect(fuel_port, fracRad_fuel.port_a) annotation(
      Line(points = {{-120, 80}, {-38, 80}}, color = {191, 0, 0}));
    connect(shield1_port, fracRad_shield1.port_a) annotation(
      Line(points = {{-120, 24}, {-38, 24}}, color = {191, 0, 0}));
    connect(TPV_port, fracRad_TPV.port_a) annotation(
      Line(points = {{-120, -30}, {-38, -30}}, color = {191, 0, 0}));
    connect(shield2_port, fracRad_shield2.port_a) annotation(
      Line(points = {{-120, -80}, {-38, -80}}, color = {191, 0, 0}));
    connect(fracRad_fuel.port_b, disk_section_heatCapacitor.port) annotation(
      Line(points = {{-6, 80}, {22, 80}, {22, -10}, {74, -10}}, color = {191, 0, 0}));
    connect(fracRad_shield1.port_b, disk_section_heatCapacitor.port) annotation(
      Line(points = {{-6, 24}, {22, 24}, {22, -10}, {74, -10}}, color = {191, 0, 0}));
    connect(fracRad_TPV.port_b, disk_section_heatCapacitor.port) annotation(
      Line(points = {{-6, -30}, {22, -30}, {22, -10}, {74, -10}}, color = {191, 0, 0}));
    connect(fracRad_shield2.port_b, disk_section_heatCapacitor.port) annotation(
      Line(points = {{-6, -80}, {22, -80}, {22, -10}, {74, -10}}, color = {191, 0, 0}));
    connect(disk_section_heatCapacitor.port, capacitor_port) annotation(
      Line(points = {{74, -10}, {74, -44}, {122, -44}}, color = {191, 0, 0}));
    annotation(
      Icon(coordinateSystem(extent = {{-100, -100}, {100, 100}}), graphics = {Rectangle(extent = {{-80, 40}, {80, -40}}), Line(points = {{-80, 0}, {-40, 0}}, thickness = 1), Line(points = {{40, 0}, {80, 0}}, thickness = 1), Line(points = {{0, 20}, {0, -20}}, thickness = 2), Text(extent = {{-70, 70}, {70, 90}}, textString = "DiskSection")}),
      Diagram(coordinateSystem(extent = {{-120, 160}, {120, -100}}), graphics = {Text(origin = {4, 56}, extent = {{-98, 84}, {98, 98}}, textString = "Radiation-scaled by fraction f")}));
  end DiskSection;

  model TwoFaceDiskSection
    import Modelica.Units.SI;
    // Parameters
    parameter SI.HeatCapacity C = 6758 "Heat capacity (J/K)";
    parameter SI.Temperature T_start = 293.15 "Start temperature";
    parameter Integer section_num = 2 "Assigned disk section";
    outer parameter Real rotRPS_common;
    outer parameter Real Gr_fuel;
    outer parameter Real Gr_shield;
    outer parameter Real Gr_tpv;
    // Half-capacity for each face
    final parameter SI.HeatCapacity C_each = C/2;
    // External port (environment side) + fraction input
    // Internals
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a fuel_port1 annotation(
      Placement(transformation(origin = {-120, 118}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 56}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield1_port1 annotation(
      Placement(transformation(origin = {-120, 100}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 26}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a TPV_port1 annotation(
      Placement(transformation(origin = {-120, 82}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -4}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield2_port1 annotation(
      Placement(transformation(origin = {-120, 64}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -36}, extent = {{-10, -10}, {10, 10}})));
    DiskSection diskSection1(C = C_each, T_start = T_start, section_num = section_num) annotation(
      Placement(transformation(origin = {65, 109}, extent = {{-19, -19}, {19, 19}})));
    DiskSection diskSection2(C = C_each, T_start = T_start, section_num = section_num) annotation(
      Placement(transformation(origin = {65, -7}, extent = {{-19, -19}, {19, 19}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b fuel_port2 annotation(
      Placement(transformation(origin = {-120, 2}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 56}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield1_port2 annotation(
      Placement(transformation(origin = {-120, -16}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 26}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b TPV_port2 annotation(
      Placement(transformation(origin = {-120, -34}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -4}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield2_port2 annotation(
      Placement(transformation(origin = {-120, -52}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -36}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Components.ThermalConductor thermalConductor(G = 18149) annotation(
      Placement(transformation(origin = {98, 52}, extent = {{-22, -22}, {22, 22}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b section_temperature_port annotation(
      Placement(transformation(origin = {120, 106}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {86, -74}, extent = {{-10, -10}, {10, 10}})));
  equation
// EXACTLY ONE thermal path: p --(port_a)-> rad --(port_b)-> cap
    connect(fuel_port1, diskSection1.fuel_port) annotation(
      Line(points = {{-120, 118}, {46, 118}}, color = {191, 0, 0}));
    connect(shield1_port1, diskSection1.shield1_port) annotation(
      Line(points = {{-120, 100}, {-22, 100}, {-22, 114}, {46, 114}}, color = {191, 0, 0}));
    connect(TPV_port1, diskSection1.TPV_port) annotation(
      Line(points = {{-120, 82}, {-12, 82}, {-12, 110}, {46, 110}}, color = {191, 0, 0}));
    connect(shield2_port1, diskSection1.shield2_port) annotation(
      Line(points = {{-120, 64}, {-2, 64}, {-2, 102}, {46, 102}}, color = {191, 0, 0}));
    connect(fuel_port2, diskSection2.fuel_port) annotation(
      Line(points = {{-120, 2}, {46, 2}}, color = {191, 0, 0}));
    connect(shield1_port2, diskSection2.shield1_port) annotation(
      Line(points = {{-120, -16}, {-24, -16}, {-24, -2}, {46, -2}}, color = {191, 0, 0}));
    connect(TPV_port2, diskSection2.TPV_port) annotation(
      Line(points = {{-120, -34}, {-8, -34}, {-8, -6}, {46, -6}}, color = {191, 0, 0}));
    connect(shield2_port2, diskSection2.shield2_port) annotation(
      Line(points = {{-120, -52}, {6, -52}, {6, -14}, {46, -14}}, color = {191, 0, 0}));
    connect(diskSection1.capacitor_port, thermalConductor.port_a) annotation(
      Line(points = {{84, 100}, {76, 100}, {76, 52}}, color = {191, 0, 0}));
    connect(diskSection2.capacitor_port, thermalConductor.port_b) annotation(
      Line(points = {{84, -16}, {120, -16}, {120, 52}}, color = {191, 0, 0}));
    connect(thermalConductor.port_a, section_temperature_port) annotation(
      Line(points = {{76, 52}, {76, 86}, {102, 86}, {102, 106}, {120, 106}}, color = {191, 0, 0}));
    annotation(
      Icon(coordinateSystem(extent = {{-100, -100}, {100, 100}}), graphics = {Rectangle(extent = {{-80, 40}, {80, -40}}), Line(points = {{-80, 0}, {-40, 0}}, thickness = 1), Line(points = {{40, 0}, {80, 0}}, thickness = 1), Line(points = {{0, 20}, {0, -20}}, thickness = 2), Text(extent = {{-70, 70}, {70, 90}}, textString = "TwoSidedDiskSection")}),
      Diagram(coordinateSystem(extent = {{-120, 160}, {120, -100}}), graphics = {Text(origin = {4, 56}, extent = {{-98, 84}, {98, 98}}, textString = "Two sided disk section")}));
  end TwoFaceDiskSection;

  model Disk
    import Modelica.Units.SI;
    // Parameters
    parameter SI.HeatCapacity heat_capacity_section = 6758 "Heat capacity (J/K)";
    parameter SI.Temperature T_start = 293.15 "Start temperature";
    // External port (environment side) + fraction input
    // Internals
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a fuel_port1 annotation(
      Placement(transformation(origin = {-120, 118}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 52}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield1_port1 annotation(
      Placement(transformation(origin = {-120, 100}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 24}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a TPV_port1 annotation(
      Placement(transformation(origin = {-120, 82}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -6}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield2_port1 annotation(
      Placement(transformation(origin = {-120, 64}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -36}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b fuel_port2 annotation(
      Placement(transformation(origin = {120, 218}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 52}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield1_port2 annotation(
      Placement(transformation(origin = {120, 200}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 24}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b TPV_port2 annotation(
      Placement(transformation(origin = {120, 182}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -6}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield2_port2 annotation(
      Placement(transformation(origin = {120, 164}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -36}, extent = {{-10, -10}, {10, 10}})));
    TwoFaceDiskSection twoFaceDiskSection1(C = heat_capacity_section, T_start = T_start, section_num = 1) annotation(
      Placement(transformation(origin = {-8, 106}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection2(C = heat_capacity_section, T_start = T_start, section_num = 2) annotation(
      Placement(transformation(origin = {-8, 72}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection3(C = heat_capacity_section, T_start = T_start, section_num = 3) annotation(
      Placement(transformation(origin = {-8, 38}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection4(C = heat_capacity_section, T_start = T_start, section_num = 4) annotation(
      Placement(transformation(origin = {-8, 2}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection5(C = heat_capacity_section, T_start = T_start, section_num = 5) annotation(
      Placement(transformation(origin = {-8, -34}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection6(C = heat_capacity_section, T_start = T_start, section_num = 6) annotation(
      Placement(transformation(origin = {-8, -70}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection7(C = heat_capacity_section, T_start = T_start, section_num = 7) annotation(
      Placement(transformation(origin = {-8, -106}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection8(C = heat_capacity_section, T_start = T_start, section_num = 8) annotation(
      Placement(transformation(origin = {-8, -146}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection9(C = heat_capacity_section, T_start = T_start, section_num = 9) annotation(
      Placement(transformation(origin = {-8, -186}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection10(C = heat_capacity_section, T_start = T_start, section_num = 10) annotation(
      Placement(transformation(origin = {-8, -224}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection11(C = heat_capacity_section, T_start = T_start, section_num = 11) annotation(
      Placement(transformation(origin = {-8, -260}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection12(C = heat_capacity_section, T_start = T_start, section_num = 12) annotation(
      Placement(transformation(origin = {-8, -300}, extent = {{-24, -24}, {24, 24}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens1 annotation(
      Placement(transformation(origin = {78, 88}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens2 annotation(
      Placement(transformation(origin = {78, 54}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens3 annotation(
      Placement(transformation(origin = {78, 20}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens4 annotation(
      Placement(transformation(origin = {78, -14}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens5 annotation(
      Placement(transformation(origin = {78, -52}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens6 annotation(
      Placement(transformation(origin = {78, -88}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens7 annotation(
      Placement(transformation(origin = {78, -124}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens8 annotation(
      Placement(transformation(origin = {78, -164}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens9 annotation(
      Placement(transformation(origin = {78, -204}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens10 annotation(
      Placement(transformation(origin = {78, -240}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens11 annotation(
      Placement(transformation(origin = {78, -278}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens12 annotation(
      Placement(transformation(origin = {78, -318}, extent = {{-14, -14}, {14, 14}})));
  equation
// EXACTLY ONE thermal path: p --(port_a)-> rad --(port_b)-> cap
    connect(fuel_port1, twoFaceDiskSection1.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-32, 118}, {-32, 119}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection1.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, 112}, {-32, 112}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection1.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, 105}, {-32, 105}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection1.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-52, 64}, {-52, 97}, {-32, 97}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection2.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-40, 118}, {-40, 85}, {-32, 85}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection2.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, 78}, {-32, 78}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection2.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, 71}, {-32, 71}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection3.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-40, 118}, {-40, 51}, {-32, 51}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection3.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, 44}, {-32, 44}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection3.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, 37}, {-32, 37}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection4.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-40, 118}, {-40, 15}, {-32, 15}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection4.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, 8}, {-32, 8}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection4.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, 1}, {-32, 1}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection4.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-52, 64}, {-52, -7}, {-32, -7}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection5.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-40, 118}, {-40, -21}, {-32, -21}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection5.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, -28}, {-32, -28}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection3.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-52, 64}, {-52, 30}, {-32, 30}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection2.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-32, 64}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection5.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, -34}, {-32, -34}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection5.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-52, 64}, {-52, -42}, {-32, -42}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection6.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-40, 118}, {-40, -56}, {-32, -56}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection6.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, -64}, {-32, -64}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection6.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, -70}, {-32, -70}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection6.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-52, 64}, {-52, -78}, {-32, -78}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection7.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-40, 118}, {-40, -92}, {-32, -92}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection7.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, -100}, {-32, -100}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection7.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, -106}, {-32, -106}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection7.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-52, 64}, {-52, -114}, {-32, -114}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection8.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-40, 118}, {-40, -132}, {-32, -132}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection8.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, -140}, {-32, -140}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection8.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, -146}, {-32, -146}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection8.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-52, 64}, {-52, -154}, {-32, -154}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection9.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-40, 118}, {-40, -172}, {-32, -172}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection9.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, -180}, {-32, -180}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection9.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, -186}, {-32, -186}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection9.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-52, 64}, {-52, -194}, {-32, -194}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection10.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-40, 118}, {-40, -210}, {-32, -210}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection10.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, -218}, {-32, -218}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection10.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, -224}, {-32, -224}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection10.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-52, 64}, {-52, -232}, {-32, -232}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection11.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-40, 118}, {-40, -246}, {-32, -246}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection11.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, -254}, {-32, -254}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection11.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, -260}, {-32, -260}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection11.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-52, 64}, {-52, -268}, {-32, -268}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection12.fuel_port1) annotation(
      Line(points = {{-120, 118}, {-40, 118}, {-40, -286}, {-32, -286}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection12.shield1_port1) annotation(
      Line(points = {{-120, 100}, {-44, 100}, {-44, -294}, {-32, -294}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection12.TPV_port1) annotation(
      Line(points = {{-120, 82}, {-48, 82}, {-48, -300}, {-32, -300}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection12.shield2_port1) annotation(
      Line(points = {{-120, 64}, {-52, 64}, {-52, -308}, {-32, -308}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection2.fuel_port2) annotation(
      Line(points = {{120, 218}, {24, 218}, {24, 86}, {16, 86}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection1.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, 112}, {16, 112}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection1.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, 106}, {16, 106}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection1.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, 98}, {16, 98}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection3.fuel_port2) annotation(
      Line(points = {{120, 218}, {24, 218}, {24, 52}, {16, 52}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection4.fuel_port2) annotation(
      Line(points = {{120, 218}, {24, 218}, {24, 16}, {16, 16}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection5.fuel_port2) annotation(
      Line(points = {{120, 218}, {24, 218}, {24, -20}, {16, -20}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection6.fuel_port2) annotation(
      Line(points = {{120, 218}, {24, 218}, {24, -56}, {16, -56}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection7.fuel_port2) annotation(
      Line(points = {{120, 218}, {24, 218}, {24, -92}, {16, -92}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection8.fuel_port2) annotation(
      Line(points = {{120, 218}, {24, 218}, {24, -132}, {16, -132}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection9.fuel_port2) annotation(
      Line(points = {{120, 218}, {24, 218}, {24, -172}, {16, -172}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection10.fuel_port2) annotation(
      Line(points = {{120, 218}, {24, 218}, {24, -210}, {16, -210}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection11.fuel_port2) annotation(
      Line(points = {{120, 218}, {24, 218}, {24, -246}, {16, -246}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection12.fuel_port2) annotation(
      Line(points = {{120, 218}, {24, 218}, {24, -286}, {16, -286}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection2.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, 78}, {16, 78}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection3.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, 44}, {16, 44}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection4.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, 8}, {16, 8}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection5.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, -28}, {16, -28}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection6.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, -64}, {16, -64}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection7.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, -100}, {16, -100}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection8.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, -140}, {16, -140}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection10.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, -218}, {16, -218}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection9.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, -180}, {16, -180}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection11.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, -254}, {16, -254}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection12.shield1_port2) annotation(
      Line(points = {{120, 200}, {28, 200}, {28, -294}, {16, -294}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection2.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, 72}, {16, 72}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection3.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, 38}, {16, 38}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection4.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, 2}, {16, 2}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection5.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, -34}, {16, -34}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection6.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, -70}, {16, -70}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection7.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, -106}, {16, -106}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection8.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, -146}, {16, -146}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection9.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, -186}, {16, -186}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection10.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, -224}, {16, -224}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection11.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, -260}, {16, -260}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection12.TPV_port2) annotation(
      Line(points = {{120, 182}, {32, 182}, {32, -300}, {16, -300}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection2.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, 64}, {16, 64}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection3.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, 30}, {16, 30}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection4.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, -6}, {16, -6}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection5.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, -42}, {16, -42}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection6.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, -78}, {16, -78}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection7.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, -114}, {16, -114}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection8.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, -154}, {16, -154}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection9.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, -194}, {16, -194}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection10.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, -232}, {16, -232}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection11.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, -268}, {16, -268}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection12.shield2_port2) annotation(
      Line(points = {{120, 164}, {36, 164}, {36, -308}, {16, -308}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection1.fuel_port2, fuel_port2) annotation(
      Line(points = {{16, 120}, {24, 120}, {24, 218}, {120, 218}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection1.section_temperature_port, tSens1.port) annotation(
      Line(points = {{12, 88}, {64, 88}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection2.section_temperature_port, tSens2.port) annotation(
      Line(points = {{12, 54}, {64, 54}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection12.section_temperature_port, tSens12.port) annotation(
      Line(points = {{12, -318}, {64, -318}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection11.section_temperature_port, tSens11.port) annotation(
      Line(points = {{12, -278}, {64, -278}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection10.section_temperature_port, tSens10.port) annotation(
      Line(points = {{12, -242}, {64, -242}, {64, -240}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection9.section_temperature_port, tSens9.port) annotation(
      Line(points = {{12, -204}, {64, -204}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection8.section_temperature_port, tSens8.port) annotation(
      Line(points = {{12, -164}, {64, -164}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection7.section_temperature_port, tSens7.port) annotation(
      Line(points = {{12, -124}, {64, -124}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection6.section_temperature_port, tSens6.port) annotation(
      Line(points = {{12, -88}, {64, -88}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection5.section_temperature_port, tSens5.port) annotation(
      Line(points = {{12, -52}, {64, -52}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection4.section_temperature_port, tSens4.port) annotation(
      Line(points = {{12, -16}, {64, -16}, {64, -14}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection3.section_temperature_port, tSens3.port) annotation(
      Line(points = {{12, 20}, {64, 20}}, color = {191, 0, 0}));
    annotation(
      Icon(coordinateSystem(extent = {{-100, -100}, {100, 100}}), graphics = {Rectangle(extent = {{-80, 40}, {80, -40}}), Line(points = {{-80, 0}, {-40, 0}}, thickness = 1), Line(points = {{40, 0}, {80, 0}}, thickness = 1), Line(points = {{0, 20}, {0, -20}}, thickness = 2), Text(extent = {{-70, 70}, {70, 90}}, textString = "Disk")}),
      Diagram(coordinateSystem(extent = {{-140, 160}, {140, -320}}), graphics = {Text(origin = {4, 56}, extent = {{-98, 84}, {98, 98}}, textString = "Disk")}));
  end Disk;

  model SwitchedThermalConductor "Lumped thermal element transporting heat without storing it"
    extends Modelica.Thermal.HeatTransfer.Interfaces.Element1D;
    parameter Real tSwitch;
    parameter Real Gon = 5 "W/K";
    parameter Real Goff = 0 "W/K";
  protected
    Real G "W/K";
  equation
// switch conductance at tSwitch
    G = if time < tSwitch then Goff else Gon;
    Q_flow = G*dT;
    annotation(
      Icon(coordinateSystem(preserveAspectRatio = true, extent = {{-100, -100}, {100, 100}}), graphics = {Rectangle(extent = {{-90, 70}, {90, -70}}, pattern = LinePattern.None, fillColor = {192, 192, 192}, fillPattern = FillPattern.Backward), Line(points = {{-90, 70}, {-90, -70}}, thickness = 0.5), Line(points = {{90, 70}, {90, -70}}, thickness = 0.5), Text(extent = {{-150, 120}, {150, 80}}, textString = "%name", textColor = {0, 0, 255}), Text(extent = {{-150, -80}, {150, -110}}, textString = "G=%G")}),
      Documentation(info = "<html>
  <p>
  This is a model for transport of heat without storing it; see also:
  <a href=\"modelica://Modelica.Thermal.HeatTransfer.Components.ThermalResistor\">ThermalResistor</a>.
  It may be used for complicated geometries where
  the thermal conductance G (= inverse of thermal resistance)
  is determined by measurements and is assumed to be constant
  over the range of operations. If the component consists mainly of
  one type of material and a regular geometry, it may be calculated,
  e.g., with one of the following equations:
  </p>
  <ul>
  <li><p>
      Conductance for a <strong>box</strong> geometry under the assumption
      that heat flows along the box length:</p>
      <blockquote><pre>
  G = k*A/L
  k: Thermal conductivity (material constant)
  A: Area of box
  L: Length of box
      </pre></blockquote>
      </li>
  <li><p>
      Conductance for a <strong>cylindrical</strong> geometry under the assumption
      that heat flows from the inside to the outside radius
      of the cylinder:</p>
      <blockquote><pre>
  G = 2*pi*k*L/log(r_out/r_in)
  pi   : Modelica.Constants.pi
  k    : Thermal conductivity (material constant)
  L    : Length of cylinder
  log  : Modelica.Math.log;
  r_out: Outer radius of cylinder
  r_in : Inner radius of cylinder
      </pre></blockquote>
      </li>
  </ul>
  <blockquote><pre>
  Typical values for k at 20 degC in W/(m.K):
    aluminium   220
    concrete      1
    copper      384
    iron         74
    silver      407
    steel        45 .. 15 (V2A)
    wood         0.1 ... 0.2
  </pre></blockquote>
  </html>"));
  end SwitchedThermalConductor;

  model GapAtmosphere
    parameter Real tSwitch;
    RIMAEL.SwitchedThermalConductor FuelGapConductor(Goff = 0, Gon = 61.6, tSwitch = tSwitch) annotation(
      Placement(transformation(origin = {-56, 2}, extent = {{-10, -10}, {10, 10}})));
    Buildings.Fluid.MixingVolumes.MixingVolume Atmosphere(redeclare package Medium = Modelica.Media.Air.DryAirNasa, V = 0.237, m_flow_nominal = 0.01, nPorts = 2) annotation(
      Placement(transformation(origin = {-14, 2}, extent = {{-10, 10}, {10, -10}}, rotation = -0)));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a port_a annotation(
      Placement(transformation(origin = {-98, 2}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-98, 2}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Fluid.Sources.Boundary_pT outerPBoundary(redeclare package Medium = Modelica.Media.Air.DryAirNasa, T = 323.15, nPorts = 2) annotation(
      Placement(transformation(origin = {-80, 74}, extent = {{-10, -10}, {10, 10}})));
    Buildings.Airflow.Multizone.MediumColumn column(h = 10, redeclare package Medium = Modelica.Media.Air.DryAirNasa, densitySelection = Buildings.Airflow.Multizone.Types.densitySelection.actual) annotation(
      Placement(transformation(origin = {86, 56}, extent = {{-10, -10}, {10, 10}})));
    Buildings.Airflow.Multizone.Orifice chimneyOrifice(redeclare package Medium = Modelica.Media.Air.DryAirNasa, m = 0.5, A = 0.283, CD = 1) annotation(
      Placement(transformation(origin = {8, 74}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Fluid.Pipes.StaticPipe dPChimney(redeclare package Medium = Modelica.Media.Air.DryAirNasa, length = 5, diameter = 0.6, roughness = 0.01, height_ab = 5) annotation(
      Placement(transformation(origin = {52, 72}, extent = {{10, -10}, {-10, 10}})));
    Modelica.Fluid.Pipes.StaticPipe dPGap(redeclare package Medium = Modelica.Media.Air.DryAirNasa, isCircular = false, crossArea = 0.002, perimeter = 2.004, length = 1, diameter = 0) annotation(
      Placement(transformation(origin = {22, 38}, extent = {{-10, -10}, {10, 10}})));
    Buildings.Airflow.Multizone.Orifice gapExitOrifice(redeclare package Medium = Modelica.Media.Air.DryAirNasa, A = 0.002) annotation(
      Placement(transformation(origin = {58, 38}, extent = {{-10, -10}, {10, 10}})));
    Buildings.Airflow.Multizone.Orifice gapEntryOrifice(redeclare package Medium = Modelica.Media.Air.DryAirNasa, A = 0.002) annotation(
      Placement(transformation(origin = {-54, 38}, extent = {{-10, -10}, {10, 10}})));
  equation
    connect(FuelGapConductor.port_b, Atmosphere.heatPort) annotation(
      Line(points = {{-46, 2}, {-24, 2}}, color = {191, 0, 0}));
    connect(port_a, FuelGapConductor.port_a) annotation(
      Line(points = {{-98, 2}, {-66, 2}}, color = {191, 0, 0}));
    connect(chimneyOrifice.port_a, outerPBoundary.ports[1]) annotation(
      Line(points = {{-2, 74}, {-70, 74}}, color = {0, 127, 255}));
    connect(chimneyOrifice.port_b, dPChimney.port_b) annotation(
      Line(points = {{18, 74}, {32, 74}, {32, 72}, {42, 72}}, color = {0, 127, 255}));
    connect(dPChimney.port_a, column.port_a) annotation(
      Line(points = {{62, 72}, {86, 72}, {86, 66}}, color = {0, 127, 255}));
    connect(dPGap.port_b, gapExitOrifice.port_a) annotation(
      Line(points = {{32, 38}, {48, 38}}, color = {0, 127, 255}));
    connect(gapExitOrifice.port_b, column.port_b) annotation(
      Line(points = {{68, 38}, {86, 38}, {86, 46}}, color = {0, 127, 255}));
    connect(outerPBoundary.ports[2], gapEntryOrifice.port_a) annotation(
      Line(points = {{-70, 74}, {-64, 74}, {-64, 38}}, color = {0, 127, 255}));
    connect(gapEntryOrifice.port_b, Atmosphere.ports[1]) annotation(
      Line(points = {{-44, 38}, {-14, 38}, {-14, 12}}, color = {0, 127, 255}));
    connect(Atmosphere.ports[2], dPGap.port_a) annotation(
      Line(points = {{-14, 12}, {-14, 38}, {12, 38}}, color = {0, 127, 255}));
    annotation(
      defaultComponentName = "vol",
      Documentation(info = ""),
      Icon(coordinateSystem(preserveAspectRatio = false, extent = {{-100, -100}, {100, 100}}), graphics = {Text(extent = {{-60, -26}, {56, -58}}, textColor = {255, 255, 255}, textString = "V=%V"), Text(extent = {{-152, 100}, {148, 140}}, textString = "%name", textColor = {0, 0, 255}), Ellipse(extent = {{-100, 98}, {100, -102}}, lineColor = {0, 0, 0}, fillPattern = FillPattern.Sphere, fillColor = DynamicSelect({170, 213, 255}, min(1, max(0, (1 - (Atmosphere.T - 273.15)/50)))*{28, 108, 200} + min(1, max(0, (Atmosphere.T - 273.15)/50))*{255, 0, 0})), Text(extent = {{62, 28}, {-58, -22}}, textColor = {255, 255, 255}, textString = DynamicSelect("", String(Atmosphere.T - 273.15, format = ".1f")))}),
      experiment(StartTime = 0, StopTime = 3000, Tolerance = 1e-06, Interval = 6));
  end GapAtmosphere;
  annotation(
    uses(Modelica(version = "4.0.0"), Buildings(version = "12.1.0")));
end RIMAEL;
