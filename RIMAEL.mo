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
    inner parameter Real tShutdown = 240 "s";
    inner parameter Real eps = 1e-6 "Avoid singularity at tau=0 (hours)";
    inner parameter Real rpsDisk = 0.2 "Rotation per second disks";
    replaceable package Medium = Modelica.Media.Air.DryAirNasa;
    inner Real rotRPS_common "rev/s";
    Modelica.Thermal.HeatTransfer.Components.HeatCapacitor FuelPlate(C = 35534, T(start = 1523.15)) annotation(
      Placement(transformation(origin = {0, 46}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sources.FixedTemperature coolWaterTemp(T = 333.15) annotation(
      Placement(transformation(origin = {2, -40}, extent = {{-10, -10}, {10, 10}})));
    Disk disk(tSwitch = tShutdown, heat_capacity_section = 23569, T_start = 1373.15) annotation(
      Placement(transformation(origin = {52, -10}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Sources.PrescribedHeatFlow prescribedHeatFlow annotation(
      Placement(transformation(origin = {-64, 32}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Blocks.Sources.RealExpression Qexpr(y = if time < tShutdown then P0 else 0.0128*P0*(max((time - tShutdown)/3600, eps)^(-0.2) - (7200 + max((time - tShutdown)/3600, eps))^(-0.2))) annotation(
      Placement(transformation(origin = {-102, 32}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Blocks.Sources.RealExpression rotationSpeed(y = if time < tShutdown then rpsDisk else 0) annotation(
      Placement(transformation(origin = {-102, 8}, extent = {{-10, -10}, {10, 10}})));
    GapAtmosphere AtmosphereFuelDisk(tSwitch = tShutdown) annotation(
      Placement(transformation(origin = {54, 56}, extent = {{10, -10}, {-10, 10}}, rotation = -0)));
    RIMAEL.GapAtmosphere AtmosphereFuelDisk1(tSwitch = tShutdown) annotation(
      Placement(transformation(origin = {54, 32}, extent = {{10, -10}, {-10, 10}})));
  equation
    rotRPS_common = rotationSpeed.y;
    connect(prescribedHeatFlow.port, FuelPlate.port) annotation(
      Line(points = {{-54, 32}, {0, 32}}, color = {191, 0, 0}));
    connect(Qexpr.y, prescribedHeatFlow.Q_flow) annotation(
      Line(points = {{-91, 32}, {-74, 32}}, color = {0, 0, 127}));
  connect(disk.fuel_port1, FuelPlate.port) annotation(
      Line(points = {{42, 0}, {0, 0}, {0, 32}}, color = {191, 0, 0}));
  connect(disk.fuel_port2, FuelPlate.port) annotation(
      Line(points = {{62, 0}, {72, 0}, {72, 8}, {0, 8}, {0, 32}}, color = {191, 0, 0}));
  connect(disk.shield1_port1, coolWaterTemp.port) annotation(
      Line(points = {{42, -2}, {30, -2}, {30, -40}, {12, -40}}, color = {191, 0, 0}));
  connect(disk.TPV_port1, coolWaterTemp.port) annotation(
      Line(points = {{42, -6}, {30, -6}, {30, -40}, {12, -40}}, color = {191, 0, 0}));
  connect(disk.shield2_port1, coolWaterTemp.port) annotation(
      Line(points = {{42, -8}, {30, -8}, {30, -40}, {12, -40}}, color = {191, 0, 0}));
  connect(disk.shield2_port_cond, coolWaterTemp.port) annotation(
      Line(points = {{42, -20}, {30, -20}, {30, -40}, {12, -40}}, color = {191, 0, 0}));
  connect(disk.TPV_port_cond, coolWaterTemp.port) annotation(
      Line(points = {{42, -16}, {30, -16}, {30, -40}, {12, -40}}, color = {191, 0, 0}));
  connect(disk.shield1_port_cond, coolWaterTemp.port) annotation(
      Line(points = {{42, -14}, {30, -14}, {30, -40}, {12, -40}}, color = {191, 0, 0}));
  connect(disk.shield1_port2, coolWaterTemp.port) annotation(
      Line(points = {{62, -2}, {72, -2}, {72, -40}, {12, -40}}, color = {191, 0, 0}));
  connect(disk.TPV_port2, coolWaterTemp.port) annotation(
      Line(points = {{62, -6}, {72, -6}, {72, -40}, {12, -40}}, color = {191, 0, 0}));
  connect(disk.shield2_port2, coolWaterTemp.port) annotation(
      Line(points = {{62, -8}, {72, -8}, {72, -40}, {12, -40}}, color = {191, 0, 0}));
  connect(disk.fuel_port_cond, AtmosphereFuelDisk1.port_a) annotation(
      Line(points = {{42, -12}, {22, -12}, {22, 16}, {70, 16}, {70, 32}, {64, 32}}, color = {191, 0, 0}));
  connect(disk.fuel_port2_cond, AtmosphereFuelDisk.port_a) annotation(
      Line(points = {{62, -12}, {84, -12}, {84, 56}, {64, 56}}, color = {191, 0, 0}));
  connect(AtmosphereFuelDisk.port_b, FuelPlate.port) annotation(
      Line(points = {{44, 56}, {28, 56}, {28, 32}, {0, 32}}, color = {191, 0, 0}));
  connect(AtmosphereFuelDisk1.port_b, FuelPlate.port) annotation(
      Line(points = {{44, 32}, {0, 32}}, color = {191, 0, 0}));
  connect(disk.shield1_port2_cond, coolWaterTemp.port) annotation(
      Line(points = {{62, -14}, {72, -14}, {72, -40}, {12, -40}}, color = {191, 0, 0}));
  connect(disk.TPV_port2_cond, coolWaterTemp.port) annotation(
      Line(points = {{62, -16}, {72, -16}, {72, -40}, {12, -40}}, color = {191, 0, 0}));
  connect(disk.shield2_port2_cond, coolWaterTemp.port) annotation(
      Line(points = {{62, -20}, {72, -20}, {72, -40}, {12, -40}}, color = {191, 0, 0}));
    annotation(
      Diagram(coordinateSystem(extent = {{-120, 100}, {180, -60}})),
      experiment(StartTime = 0, StopTime = 700, Tolerance = 1e-06, Interval = 0.2));
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
    parameter Real tSwitch;
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
      Placement(transformation(origin = {126, 152}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {80, -62}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a fuel_port annotation(
      Placement(transformation(origin = {-120, 106}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 56}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield1_port annotation(
      Placement(transformation(origin = {-120, 44}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 26}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a TPV_port annotation(
      Placement(transformation(origin = {-120, -30}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -4}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield2_port annotation(
      Placement(transformation(origin = {-120, -102}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -34}, extent = {{-10, -10}, {10, 10}})));
    FracRadiation fracRad_fuel(Gr_base = Gr_fuel) annotation(
      Placement(transformation(origin = {-3, 107}, extent = {{-15, -15}, {15, 15}})));
    FracRadiation fracRad_shield1(Gr_base = Gr_shield) annotation(
      Placement(transformation(origin = {-2, 44}, extent = {{-16, -16}, {16, 16}})));
    FracRadiation fracRad_shield2(Gr_base = Gr_shield) annotation(
      Placement(transformation(origin = {-2, -102}, extent = {{-16, -16}, {16, 16}})));
    FracRadiation fracRad_TPV(Gr_base = Gr_tpv) annotation(
      Placement(transformation(origin = {-2, -30}, extent = {{-16, -16}, {16, 16}})));
    CircularSegmentOverlapBySections circularSegmentOverlapBySections_shield2(sM = section_num, N = 12, sS1 = 12, Ls1 = 2, Lm = 2, rotRPS = rotRPS_common) annotation(
      Placement(transformation(origin = {-63, -77}, extent = {{-15, -15}, {15, 15}})));
    CircularSegmentOverlapBySections circularSegmentOverlapBySections_TPV(sM = section_num, N = 12, sS1 = 6, Ls1 = 6, Lm = 2, rotRPS = rotRPS_common) annotation(
      Placement(transformation(origin = {-63, -5}, extent = {{-15, -15}, {15, 15}})));
    CircularSegmentOverlapBySections circularSegmentOverlapBySections_fuel(N = 12, Ls1 = 2, sM = section_num, Lm = 2, sS1 = 2, rotRPS = rotRPS_common) annotation(
      Placement(transformation(origin = {-63, 127}, extent = {{-15, -15}, {15, 15}})));
    CircularSegmentOverlapBySections circularSegmentOverlapBySections_shield1(sM = section_num, N = 12, sS1 = 4, Ls1 = 2, Lm = 2, rotRPS = rotRPS_common) annotation(
      Placement(transformation(origin = {-63, 65}, extent = {{-15, -15}, {15, 15}})));
    Modelica.Thermal.HeatTransfer.Components.HeatCapacitor disk_section_heatCapacitor(C = C, T(start = T_start)) annotation(
      Placement(transformation(origin = {85, 171}, extent = {{-19, -19}, {19, 19}})));
    SwitchedThermalConductor conduction_fuel(tSwitch = tSwitch, Gon = 61.6) annotation(
      Placement(transformation(origin = {52, 108}, extent = {{10, -10}, {-10, 10}}, rotation = -0)));
    SwitchedThermalConductor conduction_shield(tSwitch = tSwitch, Gon = 61.6) annotation(
      Placement(transformation(origin = {52, 44}, extent = {{10, -10}, {-10, 10}}, rotation = -0)));
    SwitchedThermalConductor conduction_TPV(tSwitch = tSwitch, Gon = 61.6) annotation(
      Placement(transformation(origin = {52, -30}, extent = {{10, -10}, {-10, 10}}, rotation = -0)));
    SwitchedThermalConductor conduction_shield2(tSwitch = tSwitch, Gon = 61.6) annotation(
      Placement(transformation(origin = {52, -102}, extent = {{10, -10}, {-10, 10}}, rotation = -0)));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a fuel_port_cond annotation(
      Placement(transformation(origin = {126, 108}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 56}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield1_port_cond annotation(
      Placement(transformation(origin = {124, 44}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 26}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a TPV_port_cond annotation(
      Placement(transformation(origin = {122, -30}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -4}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield2_port_cond annotation(
      Placement(transformation(origin = {120, -102}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -34}, extent = {{-10, -10}, {10, 10}})));
  equation
// EXACTLY ONE thermal path: p --(port_a)-> rad --(port_b)-> cap
    connect(circularSegmentOverlapBySections_shield2.frac, fracRad_shield2.f) annotation(
      Line(points = {{-48, -77}, {-3, -77}, {-3, -87}, {-2, -87}}, color = {0, 0, 127}));
    connect(circularSegmentOverlapBySections_TPV.frac, fracRad_TPV.f) annotation(
      Line(points = {{-48, -4}, {-2, -4}, {-2, -14}, {-2, -14}}, color = {0, 0, 127}));
    connect(circularSegmentOverlapBySections_shield1.frac, fracRad_shield1.f) annotation(
      Line(points = {{-48, 65}, {-2, 65}, {-2, 59}}, color = {0, 0, 127}));
    connect(circularSegmentOverlapBySections_fuel.frac, fracRad_fuel.f) annotation(
      Line(points = {{-48, 127}, {-3, 127}, {-3, 122}}, color = {0, 0, 127}));
    connect(fuel_port, fracRad_fuel.port_a) annotation(
      Line(points = {{-120, 106}, {-79, 106}, {-79, 107}, {-18, 107}}, color = {191, 0, 0}));
    connect(shield1_port, fracRad_shield1.port_a) annotation(
      Line(points = {{-120, 44}, {-18, 44}}, color = {191, 0, 0}));
    connect(TPV_port, fracRad_TPV.port_a) annotation(
      Line(points = {{-120, -30}, {-18, -30}}, color = {191, 0, 0}));
    connect(shield2_port, fracRad_shield2.port_a) annotation(
      Line(points = {{-120, -102}, {-18, -102}}, color = {191, 0, 0}));
    connect(fracRad_fuel.port_b, disk_section_heatCapacitor.port) annotation(
      Line(points = {{12, 107}, {22, 107}, {22, 152}, {85, 152}}, color = {191, 0, 0}));
    connect(fracRad_TPV.port_b, disk_section_heatCapacitor.port) annotation(
      Line(points = {{14, -30}, {22, -30}, {22, 152}, {85, 152}}, color = {191, 0, 0}));
    connect(fracRad_shield2.port_b, disk_section_heatCapacitor.port) annotation(
      Line(points = {{14, -102}, {22, -102}, {22, 152}, {85, 152}}, color = {191, 0, 0}));
    connect(disk_section_heatCapacitor.port, capacitor_port) annotation(
      Line(points = {{85, 152}, {126, 152}}, color = {191, 0, 0}));
    connect(circularSegmentOverlapBySections_fuel.frac, conduction_fuel.f) annotation(
      Line(points = {{-48, 128}, {52, 128}, {52, 118}}, color = {0, 0, 127}));
    connect(disk_section_heatCapacitor.port, conduction_shield.port_b) annotation(
      Line(points = {{85, 152}, {22, 152}, {22, 44}, {42, 44}}, color = {191, 0, 0}));
    connect(disk_section_heatCapacitor.port, conduction_TPV.port_b) annotation(
      Line(points = {{85, 152}, {22, 152}, {22, -30}, {42, -30}}, color = {191, 0, 0}));
    connect(circularSegmentOverlapBySections_TPV.frac, conduction_TPV.f) annotation(
      Line(points = {{-48, -4}, {52, -4}, {52, -20}}, color = {0, 0, 127}));
    connect(disk_section_heatCapacitor.port, conduction_shield2.port_b) annotation(
      Line(points = {{85, 152}, {22, 152}, {22, -102}, {42, -102}}, color = {191, 0, 0}));
    connect(circularSegmentOverlapBySections_shield2.frac, conduction_shield2.f) annotation(
      Line(points = {{-48, -76}, {52, -76}, {52, -92}}, color = {0, 0, 127}));
    connect(disk_section_heatCapacitor.port, fracRad_shield1.port_b) annotation(
      Line(points = {{86, 152}, {22, 152}, {22, 44}, {14, 44}}, color = {191, 0, 0}));
    connect(disk_section_heatCapacitor.port, conduction_fuel.port_b) annotation(
      Line(points = {{86, 152}, {22, 152}, {22, 108}, {42, 108}}, color = {191, 0, 0}));
    connect(circularSegmentOverlapBySections_shield1.frac, conduction_shield.f) annotation(
      Line(points = {{-48, 66}, {52, 66}, {52, 54}}, color = {0, 0, 127}));
    connect(conduction_shield2.port_a, shield2_port_cond) annotation(
      Line(points = {{62, -102}, {120, -102}}, color = {191, 0, 0}));
    connect(TPV_port_cond, conduction_TPV.port_a) annotation(
      Line(points = {{122, -30}, {62, -30}}, color = {191, 0, 0}));
    connect(conduction_fuel.port_a, fuel_port_cond) annotation(
      Line(points = {{62, 108}, {126, 108}}, color = {191, 0, 0}));
    connect(conduction_shield.port_a, shield1_port_cond) annotation(
      Line(points = {{62, 44}, {124, 44}}, color = {191, 0, 0}));
    annotation(
      Icon(coordinateSystem(extent = {{-100, -100}, {100, 100}}), graphics = {Rectangle(extent = {{-80, 40}, {80, -40}}), Line(points = {{-80, 0}, {-40, 0}}, thickness = 1), Line(points = {{40, 0}, {80, 0}}, thickness = 1), Line(points = {{0, 20}, {0, -20}}, thickness = 2), Text(extent = {{-70, 70}, {70, 90}}, textString = "DiskSection")}),
      Diagram(coordinateSystem(extent = {{-140, 160}, {140, -140}}), graphics = {Text(origin = {2, 122}, extent = {{-98, 84}, {98, 98}}, textString = "Disc section
Radiation and conduction simulated depending on disc section position", textStyle = {TextStyle.Bold})}));
  end DiskSection;

  model TwoFaceDiskSection
    import Modelica.Units.SI;
    parameter Real tSwitch;
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
      Placement(transformation(origin = {-120, 118}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-102, 98}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield1_port1 annotation(
      Placement(transformation(origin = {-120, 100}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-102, 70}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a TPV_port1 annotation(
      Placement(transformation(origin = {-120, 82}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-102, 42}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield2_port1 annotation(
      Placement(transformation(origin = {-120, 64}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-102, 14}, extent = {{-10, -10}, {10, 10}})));
    DiskSection diskSection1(tSwitch = tSwitch, C = C_each, T_start = T_start, section_num = section_num) annotation(
      Placement(transformation(origin = {-51, 107}, extent = {{-19, -19}, {19, 19}})));
    DiskSection diskSection2(tSwitch = tSwitch, C = C_each, T_start = T_start, section_num = section_num) annotation(
      Placement(transformation(origin = {-51, -9}, extent = {{-19, -19}, {19, 19}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b fuel_port2 annotation(
      Placement(transformation(origin = {-120, 2}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 98}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield1_port2 annotation(
      Placement(transformation(origin = {-120, -16}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 70}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b TPV_port2 annotation(
      Placement(transformation(origin = {-120, -34}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 42}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield2_port2 annotation(
      Placement(transformation(origin = {-120, -52}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 14}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Components.ThermalConductor thermalConductor(G = 18149) annotation(
      Placement(transformation(origin = {-12, 52}, extent = {{-22, -22}, {22, 22}}, rotation = -90)));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b section_temperature_port annotation(
      Placement(transformation(origin = {118, 44}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {42, -60}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b fuel_port_cond2 annotation(
      Placement(transformation(origin = {122, 2}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -14}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield1_port_cond2 annotation(
      Placement(transformation(origin = {122, -20}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -42}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b TPV_port_cond2 annotation(
      Placement(transformation(origin = {122, -40}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -70}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a fuel_port_cond annotation(
      Placement(transformation(origin = {120, 138}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-102, -14}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a TPV_port_cond annotation(
      Placement(transformation(origin = {120, 98}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-102, -70}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield1_port_cond annotation(
      Placement(transformation(origin = {120, 118}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-102, -42}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield2_port_cond annotation(
      Placement(transformation(origin = {120, 78}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-102, -98}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield2_port_cond2 annotation(
      Placement(transformation(origin = {122, -60}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -98}, extent = {{-10, -10}, {10, 10}})));
  equation
// EXACTLY ONE thermal path: p --(port_a)-> rad --(port_b)-> cap
    connect(fuel_port1, diskSection1.fuel_port) annotation(
      Line(points = {{-120, 118}, {-70, 118}}, color = {191, 0, 0}));
    connect(fuel_port2, diskSection2.fuel_port) annotation(
      Line(points = {{-120, 2}, {-70, 2}}, color = {191, 0, 0}));
    connect(thermalConductor.port_a, section_temperature_port) annotation(
      Line(points = {{-12, 74}, {44, 74}, {44, 44}, {118, 44}}, color = {191, 0, 0}));
    connect(shield2_port1, diskSection1.shield2_port) annotation(
      Line(points = {{-120, 64}, {-88, 64}, {-88, 100}, {-70, 100}}, color = {191, 0, 0}));
    connect(TPV_port1, diskSection1.TPV_port) annotation(
      Line(points = {{-120, 82}, {-92, 82}, {-92, 106}, {-70, 106}}, color = {191, 0, 0}));
    connect(shield1_port1, diskSection1.shield1_port) annotation(
      Line(points = {{-120, 100}, {-96, 100}, {-96, 112}, {-70, 112}}, color = {191, 0, 0}));
    connect(shield1_port2, diskSection2.shield1_port) annotation(
      Line(points = {{-120, -16}, {-108, -16}, {-108, -4}, {-70, -4}}, color = {191, 0, 0}));
    connect(TPV_port2, diskSection2.TPV_port) annotation(
      Line(points = {{-120, -34}, {-102, -34}, {-102, -10}, {-70, -10}}, color = {191, 0, 0}));
    connect(shield2_port2, diskSection2.shield2_port) annotation(
      Line(points = {{-120, -52}, {-98, -52}, {-98, -16}, {-70, -16}}, color = {191, 0, 0}));
    connect(diskSection2.fuel_port_cond, fuel_port_cond2) annotation(
      Line(points = {{-32, 2}, {122, 2}}, color = {191, 0, 0}));
    connect(diskSection2.shield1_port_cond, shield1_port_cond2) annotation(
      Line(points = {{-32, -4}, {76, -4}, {76, -20}, {122, -20}}, color = {191, 0, 0}));
    connect(diskSection2.TPV_port_cond, TPV_port_cond2) annotation(
      Line(points = {{-32, -10}, {70, -10}, {70, -40}, {122, -40}}, color = {191, 0, 0}));
    connect(diskSection1.fuel_port_cond, fuel_port_cond) annotation(
      Line(points = {{-32, 118}, {62, 118}, {62, 138}, {120, 138}}, color = {191, 0, 0}));
    connect(diskSection1.shield1_port_cond, shield1_port_cond) annotation(
      Line(points = {{-32, 112}, {70, 112}, {70, 118}, {120, 118}}, color = {191, 0, 0}));
    connect(diskSection1.TPV_port_cond, TPV_port_cond) annotation(
      Line(points = {{-32, 106}, {70, 106}, {70, 98}, {120, 98}}, color = {191, 0, 0}));
    connect(diskSection1.shield2_port_cond, shield2_port_cond) annotation(
      Line(points = {{-32, 100}, {62, 100}, {62, 78}, {120, 78}}, color = {191, 0, 0}));
    connect(diskSection2.capacitor_port, thermalConductor.port_b) annotation(
      Line(points = {{-36, -20}, {-36, -50}, {-12, -50}, {-12, 30}}, color = {191, 0, 0}));
    connect(diskSection1.capacitor_port, thermalConductor.port_a) annotation(
      Line(points = {{-36, 96}, {-12, 96}, {-12, 74}}, color = {191, 0, 0}));
    connect(diskSection2.shield2_port_cond, shield2_port_cond2) annotation(
      Line(points = {{-32, -16}, {50, -16}, {50, -60}, {122, -60}}, color = {191, 0, 0}));
    annotation(
      Icon(coordinateSystem(extent = {{-100, -100}, {100, 100}}), graphics = {Rectangle(extent = {{-80, 40}, {80, -40}}), Line(points = {{-80, 0}, {-40, 0}}, thickness = 1), Line(points = {{40, 0}, {80, 0}}, thickness = 1), Line(points = {{0, 20}, {0, -20}}, thickness = 2), Text(origin = {0, -20}, extent = {{-70, 70}, {70, 90}}, textString = "TwoSidedDiskSection"), Line(origin = {-7, 0}, points = {{-139, 0}, {-77, 0}, {139, 0}}), Text(origin = {0, -75}, extent = {{-28, 15}, {28, -15}}, textString = "conduction"), Text(origin = {2, 85}, extent = {{-28, 15}, {28, -15}}, textString = "radiation")}),
      Diagram(coordinateSystem(extent = {{-120, 160}, {120, -100}}), graphics = {Text(origin = {4, 56}, extent = {{-98, 84}, {98, 98}}, textString = "Two sided disk section")}));
  end TwoFaceDiskSection;

  model Disk
    import Modelica.Units.SI;
    parameter Real tSwitch;
    // Parameters
    parameter SI.HeatCapacity heat_capacity_section = 6758 "Heat capacity (J/K)";
    parameter SI.Temperature T_start = 293.15 "Start temperature";
    // External port (environment side) + fraction input
    // Internals
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a fuel_port1 annotation(
      Placement(transformation(origin = {-130, 284}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 98}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield1_port1 annotation(
      Placement(transformation(origin = {-130, 266}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 70}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a TPV_port1 annotation(
      Placement(transformation(origin = {-130, 248}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 42}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield2_port1 annotation(
      Placement(transformation(origin = {-130, 230}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, 14}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b fuel_port2 annotation(
      Placement(transformation(origin = {116, 274}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 98}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield1_port2 annotation(
      Placement(transformation(origin = {116, 256}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 70}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b TPV_port2 annotation(
      Placement(transformation(origin = {116, 238}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 42}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield2_port2 annotation(
      Placement(transformation(origin = {116, 220}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 14}, extent = {{-10, -10}, {10, 10}})));
    TwoFaceDiskSection twoFaceDiskSection1(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 1) annotation(
      Placement(transformation(origin = {-16, 196}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection2(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 2) annotation(
      Placement(transformation(origin = {-16, 142}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection3(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 3) annotation(
      Placement(transformation(origin = {-16, 88}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection4(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 4) annotation(
      Placement(transformation(origin = {-16, 34}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection5(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 5) annotation(
      Placement(transformation(origin = {-16, -20}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection6(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 6) annotation(
      Placement(transformation(origin = {-16, -74}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection7(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 7) annotation(
      Placement(transformation(origin = {-16, -128}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection8(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 8) annotation(
      Placement(transformation(origin = {-16, -182}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection9(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 9) annotation(
      Placement(transformation(origin = {-16, -236}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection10(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 10) annotation(
      Placement(transformation(origin = {-16, -290}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection11(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 11) annotation(
      Placement(transformation(origin = {-16, -344}, extent = {{-24, -24}, {24, 24}})));
    TwoFaceDiskSection twoFaceDiskSection12(tSwitch = tSwitch, C = heat_capacity_section, T_start = T_start, section_num = 12) annotation(
      Placement(transformation(origin = {-16, -398}, extent = {{-24, -24}, {24, 24}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens1 annotation(
      Placement(transformation(origin = {92, 182}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens2 annotation(
      Placement(transformation(origin = {92, 128}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens3 annotation(
      Placement(transformation(origin = {92, 74}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens4 annotation(
      Placement(transformation(origin = {92, 20}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens5 annotation(
      Placement(transformation(origin = {92, -34}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens6 annotation(
      Placement(transformation(origin = {92, -88}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens7 annotation(
      Placement(transformation(origin = {92, -142}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens8 annotation(
      Placement(transformation(origin = {92, -196}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens9 annotation(
      Placement(transformation(origin = {92, -250}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens10 annotation(
      Placement(transformation(origin = {92, -304}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens11 annotation(
      Placement(transformation(origin = {92, -358}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Sensors.TemperatureSensor tSens12 annotation(
      Placement(transformation(origin = {92, -412}, extent = {{-14, -14}, {14, 14}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a fuel_port_cond annotation(
      Placement(transformation(origin = {-130, 130}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -14}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield1_port_cond annotation(
      Placement(transformation(origin = {-130, 112}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -42}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a TPV_port_cond annotation(
      Placement(transformation(origin = {-130, 94}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -70}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a shield2_port_cond annotation(
      Placement(transformation(origin = {-130, 74}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-100, -98}, extent = {{-10, -10}, {10, 10}})));
  Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b fuel_port2_cond annotation(
      Placement(transformation(origin = {120, 134}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -14}, extent = {{-10, -10}, {10, 10}})));
  Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield1_port2_cond annotation(
      Placement(transformation(origin = {120, 116}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -42}, extent = {{-10, -10}, {10, 10}})));
  Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b TPV_port2_cond annotation(
      Placement(transformation(origin = {120, 98}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -70}, extent = {{-10, -10}, {10, 10}})));
  Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b shield2_port2_cond annotation(
      Placement(transformation(origin = {120, 78}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, -98}, extent = {{-10, -10}, {10, 10}})));
  equation
// EXACTLY ONE thermal path: p --(port_a)-> rad --(port_b)-> cap
    connect(fuel_port1, twoFaceDiskSection1.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-85, 284}, {-85, 220}, {-40, 220}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection1.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, 213}, {-40, 213}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection1.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-85, 248}, {-85, 206}, {-40, 206}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection1.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, 199}, {-40, 199}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection2.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-48, 284}, {-48, 166}, {-40, 166}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection2.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, 159}, {-40, 159}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection2.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-56, 248}, {-56, 152}, {-40, 152}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection3.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-48, 284}, {-48, 112}, {-40, 112}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection3.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, 105}, {-40, 105}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection3.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-56, 248}, {-56, 98}, {-40, 98}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection4.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-48, 284}, {-48, 58}, {-40, 58}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection4.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, 51}, {-40, 51}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection4.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-56, 248}, {-56, 44}, {-40, 44}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection4.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, 37}, {-40, 37}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection5.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-48, 284}, {-48, 4}, {-40, 4}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection5.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, -3}, {-40, -3}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection3.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, 91}, {-40, 91}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection2.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, 145}, {-40, 145}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection5.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-56, 248}, {-56, -10}, {-40, -10}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection5.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, -17}, {-40, -17}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection6.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-48, 284}, {-48, -50}, {-40, -50}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection6.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, -57}, {-40, -57}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection6.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-56, 248}, {-56, -64}, {-40, -64}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection6.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, -71}, {-40, -71}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection7.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-48, 284}, {-48, -104}, {-40, -104}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection7.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, -111}, {-40, -111}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection7.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-56, 248}, {-56, -118}, {-40, -118}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection7.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, -125}, {-40, -125}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection8.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-48, 284}, {-48, -158}, {-40, -158}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection8.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, -165}, {-40, -165}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection8.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-56, 248}, {-56, -172}, {-40, -172}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection8.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, -179}, {-40, -179}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection9.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-48, 284}, {-48, -212}, {-40, -212}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection9.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, -219}, {-40, -219}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection9.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-56, 248}, {-56, -226}, {-40, -226}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection9.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, -233}, {-40, -233}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection10.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-48, 284}, {-48, -266}, {-40, -266}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection10.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, -273}, {-40, -273}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection10.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-56, 248}, {-56, -280}, {-40, -280}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection10.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, -287}, {-40, -287}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection11.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-48, 284}, {-48, -320}, {-40, -320}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection11.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, -327}, {-40, -327}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection11.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-56, 248}, {-56, -334}, {-40, -334}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection11.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, -341}, {-40, -341}}, color = {191, 0, 0}));
    connect(fuel_port1, twoFaceDiskSection12.fuel_port1) annotation(
      Line(points = {{-130, 284}, {-48, 284}, {-48, -374}, {-40, -374}}, color = {191, 0, 0}));
    connect(shield1_port1, twoFaceDiskSection12.shield1_port1) annotation(
      Line(points = {{-130, 266}, {-52, 266}, {-52, -381}, {-40, -381}}, color = {191, 0, 0}));
    connect(TPV_port1, twoFaceDiskSection12.TPV_port1) annotation(
      Line(points = {{-130, 248}, {-56, 248}, {-56, -388}, {-40, -388}}, color = {191, 0, 0}));
    connect(shield2_port1, twoFaceDiskSection12.shield2_port1) annotation(
      Line(points = {{-130, 230}, {-60, 230}, {-60, -395}, {-40, -395}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection2.fuel_port2) annotation(
      Line(points = {{116, 274}, {20, 274}, {20, 166}, {8, 166}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection1.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, 213}, {8, 213}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection1.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, 206}, {8, 206}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection1.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, 199}, {8, 199}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection3.fuel_port2) annotation(
      Line(points = {{116, 274}, {20, 274}, {20, 112}, {8, 112}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection4.fuel_port2) annotation(
      Line(points = {{116, 274}, {20, 274}, {20, 58}, {8, 58}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection5.fuel_port2) annotation(
      Line(points = {{116, 274}, {20, 274}, {20, 4}, {8, 4}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection6.fuel_port2) annotation(
      Line(points = {{116, 274}, {20, 274}, {20, -50}, {8, -50}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection7.fuel_port2) annotation(
      Line(points = {{116, 274}, {20, 274}, {20, -104}, {8, -104}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection8.fuel_port2) annotation(
      Line(points = {{116, 274}, {20, 274}, {20, -158}, {8, -158}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection9.fuel_port2) annotation(
      Line(points = {{116, 274}, {20, 274}, {20, -212}, {8, -212}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection10.fuel_port2) annotation(
      Line(points = {{116, 274}, {20, 274}, {20, -266}, {8, -266}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection11.fuel_port2) annotation(
      Line(points = {{116, 274}, {20, 274}, {20, -320}, {8, -320}}, color = {191, 0, 0}));
    connect(fuel_port2, twoFaceDiskSection12.fuel_port2) annotation(
      Line(points = {{116, 274}, {20, 274}, {20, -374}, {8, -374}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection2.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, 159}, {8, 159}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection3.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, 105}, {8, 105}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection4.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, 51}, {8, 51}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection5.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, -3}, {8, -3}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection6.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, -57}, {8, -57}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection7.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, -111}, {8, -111}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection8.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, -165}, {8, -165}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection10.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, -273}, {8, -273}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection9.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, -219}, {8, -219}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection11.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, -327}, {8, -327}}, color = {191, 0, 0}));
    connect(shield1_port2, twoFaceDiskSection12.shield1_port2) annotation(
      Line(points = {{116, 256}, {24, 256}, {24, -381}, {8, -381}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection2.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, 152}, {8, 152}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection3.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, 98}, {8, 98}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection4.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, 44}, {8, 44}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection5.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, -10}, {8, -10}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection6.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, -64}, {8, -64}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection7.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, -118}, {8, -118}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection8.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, -172}, {8, -172}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection9.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, -226}, {8, -226}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection10.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, -280}, {8, -280}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection11.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, -334}, {8, -334}}, color = {191, 0, 0}));
    connect(TPV_port2, twoFaceDiskSection12.TPV_port2) annotation(
      Line(points = {{116, 238}, {28, 238}, {28, -388}, {8, -388}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection2.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, 145}, {8, 145}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection3.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, 91}, {8, 91}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection4.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, 37}, {8, 37}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection5.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, -17}, {8, -17}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection6.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, -71}, {8, -71}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection7.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, -125}, {8, -125}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection8.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, -179}, {8, -179}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection9.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, -233}, {8, -233}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection10.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, -287}, {8, -287}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection11.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, -341}, {8, -341}}, color = {191, 0, 0}));
    connect(shield2_port2, twoFaceDiskSection12.shield2_port2) annotation(
      Line(points = {{116, 220}, {32, 220}, {32, -395}, {8, -395}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection1.fuel_port2, fuel_port2) annotation(
      Line(points = {{8, 219.52}, {20, 219.52}, {20, 282.56}, {116, 282.56}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection1.section_temperature_port, tSens1.port) annotation(
      Line(points = {{-5.92, 181.6}, {20.16, 181.6}, {20.16, 182}, {78, 182}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection2.section_temperature_port, tSens2.port) annotation(
      Line(points = {{-5.92, 127.6}, {20.16, 127.6}, {20.16, 128}, {78, 128}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection12.section_temperature_port, tSens12.port) annotation(
      Line(points = {{-5.92, -412.4}, {19.58, -412.4}, {19.58, -412}, {78, -412}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection11.section_temperature_port, tSens11.port) annotation(
      Line(points = {{-5.92, -358.4}, {20.16, -358.4}, {20.16, -358}, {78, -358}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection10.section_temperature_port, tSens10.port) annotation(
      Line(points = {{-5.92, -304.4}, {78, -304.4}, {78, -304}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection9.section_temperature_port, tSens9.port) annotation(
      Line(points = {{-5.92, -250.4}, {20.16, -250.4}, {20.16, -250}, {78, -250}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection8.section_temperature_port, tSens8.port) annotation(
      Line(points = {{-5.92, -196.4}, {20.16, -196.4}, {20.16, -196}, {78, -196}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection7.section_temperature_port, tSens7.port) annotation(
      Line(points = {{-5.92, -142.4}, {20.16, -142.4}, {20.16, -142}, {78, -142}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection6.section_temperature_port, tSens6.port) annotation(
      Line(points = {{-5.92, -88.4}, {20.16, -88.4}, {20.16, -88}, {78, -88}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection5.section_temperature_port, tSens5.port) annotation(
      Line(points = {{-5.92, -34.4}, {20.16, -34.4}, {20.16, -34}, {78, -34}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection4.section_temperature_port, tSens4.port) annotation(
      Line(points = {{-5.92, 19.6}, {78, 19.6}, {78, 20}}, color = {191, 0, 0}));
    connect(twoFaceDiskSection3.section_temperature_port, tSens3.port) annotation(
      Line(points = {{-5.92, 73.6}, {20.16, 73.6}, {20.16, 74}, {78, 74}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection1.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, 192}, {-40, 192}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection1.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, 186}, {-40, 186}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection1.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, 180}, {-40, 180}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection1.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, 172}, {-40, 172}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection2.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, 138}, {-40, 138}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection2.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, 132}, {-40, 132}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection2.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, 126}, {-40, 126}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection2.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, 118}, {-40, 118}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection3.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, 84}, {-40, 84}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection3.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, 78}, {-40, 78}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection3.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, 72}, {-40, 72}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection3.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, 64}, {-40, 64}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection4.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, 30}, {-40, 30}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection4.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, 24}, {-40, 24}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection4.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, 18}, {-40, 18}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection4.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, 10}, {-40, 10}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection5.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, -24}, {-40, -24}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection5.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, -30}, {-40, -30}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection5.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, -36}, {-40, -36}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection5.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, -44}, {-40, -44}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection6.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, -78}, {-40, -78}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection6.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, -84}, {-40, -84}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection6.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, -90}, {-40, -90}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection6.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, -98}, {-40, -98}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection7.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, -132}, {-40, -132}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection7.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, -138}, {-40, -138}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection7.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, -144}, {-40, -144}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection7.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, -152}, {-40, -152}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection8.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, -186}, {-40, -186}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection8.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, -192}, {-40, -192}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection8.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, -198}, {-40, -198}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection8.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, -206}, {-40, -206}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection9.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, -240}, {-40, -240}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection9.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, -246}, {-40, -246}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection9.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, -252}, {-40, -252}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection9.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, -260}, {-40, -260}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection10.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, -294}, {-40, -294}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection10.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, -300}, {-40, -300}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection10.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, -306}, {-40, -306}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection10.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, -314}, {-40, -314}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection11.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, -348}, {-40, -348}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection11.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, -354}, {-40, -354}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection11.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, -360}, {-40, -360}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection11.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, -368}, {-40, -368}}, color = {191, 0, 0}));
  connect(fuel_port_cond, twoFaceDiskSection12.fuel_port_cond) annotation(
      Line(points = {{-130, 130}, {-72, 130}, {-72, -402}, {-40, -402}}, color = {191, 0, 0}));
  connect(shield1_port_cond, twoFaceDiskSection12.shield1_port_cond) annotation(
      Line(points = {{-130, 112}, {-76, 112}, {-76, -408}, {-40, -408}}, color = {191, 0, 0}));
  connect(TPV_port_cond, twoFaceDiskSection12.TPV_port_cond) annotation(
      Line(points = {{-130, 94}, {-80, 94}, {-80, -414}, {-40, -414}}, color = {191, 0, 0}));
  connect(shield2_port_cond, twoFaceDiskSection12.shield2_port_cond) annotation(
      Line(points = {{-130, 74}, {-84, 74}, {-84, -422}, {-40, -422}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection1.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, 192}, {8, 192}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection1.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, 186}, {8, 186}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection1.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, 180}, {8, 180}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection1.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, 172}, {8, 172}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection2.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, 138}, {8, 138}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection2.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, 132}, {8, 132}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection2.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, 126}, {8, 126}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection2.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, 118}, {8, 118}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection3.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, 84}, {8, 84}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection3.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, 78}, {8, 78}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection3.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, 72}, {8, 72}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection3.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, 64}, {8, 64}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection4.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, 30}, {8, 30}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection4.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, 24}, {8, 24}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection4.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, 18}, {8, 18}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection4.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, 10}, {8, 10}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection5.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, -24}, {8, -24}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection5.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, -30}, {8, -30}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection5.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, -36}, {8, -36}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection5.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, -44}, {8, -44}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection6.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, -78}, {8, -78}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection6.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, -84}, {8, -84}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection6.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, -90}, {8, -90}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection6.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, -98}, {8, -98}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection7.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, -132}, {8, -132}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection7.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, -138}, {8, -138}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection7.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, -144}, {8, -144}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection7.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, -152}, {8, -152}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection8.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, -186}, {8, -186}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection8.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, -192}, {8, -192}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection8.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, -198}, {8, -198}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection8.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, -206}, {8, -206}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection9.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, -240}, {8, -240}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection9.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, -246}, {8, -246}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection9.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, -252}, {8, -252}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection9.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, -260}, {8, -260}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection10.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, -294}, {8, -294}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection10.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, -300}, {8, -300}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection10.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, -306}, {8, -306}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection10.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, -314}, {8, -314}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection11.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, -348}, {8, -348}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection11.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, -354}, {8, -354}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection11.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, -360}, {8, -360}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection11.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, -368}, {8, -368}}, color = {191, 0, 0}));
  connect(fuel_port2_cond, twoFaceDiskSection12.fuel_port_cond2) annotation(
      Line(points = {{120, 134}, {44, 134}, {44, -402}, {8, -402}}, color = {191, 0, 0}));
  connect(shield1_port2_cond, twoFaceDiskSection12.shield1_port_cond2) annotation(
      Line(points = {{120, 116}, {48, 116}, {48, -408}, {8, -408}}, color = {191, 0, 0}));
  connect(TPV_port2_cond, twoFaceDiskSection12.TPV_port_cond2) annotation(
      Line(points = {{120, 98}, {52, 98}, {52, -414}, {8, -414}}, color = {191, 0, 0}));
  connect(shield2_port2_cond, twoFaceDiskSection12.shield2_port_cond2) annotation(
      Line(points = {{120, 78}, {56, 78}, {56, -422}, {8, -422}}, color = {191, 0, 0}));
    annotation(
      Icon(coordinateSystem(extent = {{-100, -100}, {100, 100}}), graphics = {Rectangle(extent = {{-80, 40}, {80, -40}}), Line(points = {{-80, 0}, {-40, 0}}, thickness = 1), Line(points = {{40, 0}, {80, 0}}, thickness = 1), Line(points = {{0, 20}, {0, -20}}, thickness = 2), Text(extent = {{-70, 70}, {70, 90}}, textString = "Disk"), Line(origin = {2, 0}, points = {{-112, 0}, {112, 0}, {112, 0}, {112, 0}})}),
      Diagram(coordinateSystem(extent = {{-140, 300}, {140, -420}})));
  end Disk;

  model SwitchedThermalConductor "Lumped thermal element transporting heat without storing it"
    extends Modelica.Thermal.HeatTransfer.Interfaces.Element1D;
    parameter Real tSwitch;
    parameter Real Gon = 5 "W/K";
    parameter Real Goff = 0 "W/K";
    Modelica.Blocks.Interfaces.RealInput f "Visible/view fraction 0..1" annotation(
      Placement(transformation(extent = {{-10, 90}, {10, 110}}), iconTransformation(extent = {{-10, 90}, {10, 110}})));
  protected
    Real G "W/K";
    Real fclamped;
  equation
    fclamped = max(0, min(1, f));
// switch conductance at tSwitch
    G = if time < tSwitch then Goff else Gon;
    Q_flow = fclamped*G*dT;
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
      Placement(transformation(origin = {-46, -60}, extent = {{-10, -10}, {10, 10}})));
    Buildings.Fluid.MixingVolumes.MixingVolume Atmosphere(redeclare package Medium = Modelica.Media.Air.DryAirNasa, V = 0.237, m_flow_nominal = 0.01, nPorts = 2) annotation(
      Placement(transformation(origin = {-14, -30}, extent = {{-10, 10}, {10, -10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a port_a annotation(
      Placement(transformation(origin = {-116, -18}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {-98, 0}, extent = {{-10, -10}, {10, 10}})));
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
    Modelica.Blocks.Sources.RealExpression fractionalConductance(y = 1) annotation(
      Placement(transformation(origin = {-68, -42}, extent = {{-10, -10}, {10, 10}})));
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b port_b annotation(
      Placement(transformation(origin = {-116, -60}, extent = {{-10, -10}, {10, 10}}), iconTransformation(origin = {100, 0}, extent = {{-10, -10}, {10, 10}})));
  equation
    connect(FuelGapConductor.port_b, Atmosphere.heatPort) annotation(
      Line(points = {{-36, -60}, {-35, -60}, {-35, -30}, {-24, -30}}, color = {191, 0, 0}));
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
      Line(points = {{-44, 38}, {-44, 36}, {-14, 36}, {-14, -20}}, color = {0, 127, 255}));
    connect(Atmosphere.ports[2], dPGap.port_a) annotation(
      Line(points = {{-14, -20}, {-14, 38}, {12, 38}}, color = {0, 127, 255}));
    connect(fractionalConductance.y, FuelGapConductor.f) annotation(
      Line(points = {{-57, -42}, {-47, -42}, {-47, -50}}, color = {0, 0, 127}));
    connect(FuelGapConductor.port_a, port_b) annotation(
      Line(points = {{-56, -60}, {-116, -60}}, color = {191, 0, 0}));
  connect(Atmosphere.heatPort, port_a) annotation(
      Line(points = {{-24, -30}, {-34, -30}, {-34, -18}, {-116, -18}}, color = {191, 0, 0}));
    annotation(
      defaultComponentName = "vol",
      Documentation(info = ""),
      Icon(coordinateSystem(preserveAspectRatio = false, extent = {{-100, -100}, {100, 100}}), graphics = {Text(extent = {{-60, -26}, {56, -58}}, textColor = {255, 255, 255}, textString = "V=%V"), Text(extent = {{-152, 100}, {148, 140}}, textString = "%name", textColor = {0, 0, 255}), Ellipse(extent = {{-100, 98}, {100, -102}}, lineColor = {0, 0, 0}, fillPattern = FillPattern.Sphere, fillColor = DynamicSelect({170, 213, 255}, min(1, max(0, (1 - (Atmosphere.T - 273.15)/50)))*{28, 108, 200} + min(1, max(0, (Atmosphere.T - 273.15)/50))*{255, 0, 0})), Text(extent = {{62, 28}, {-58, -22}}, textColor = {255, 255, 255}, textString = DynamicSelect("", String(Atmosphere.T - 273.15, format = ".1f")))}),
      experiment(StartTime = 0, StopTime = 3000, Tolerance = 1e-06, Interval = 6),
      Diagram(coordinateSystem(extent = {{-120, 100}, {100, -80}})));
  end GapAtmosphere;
  annotation(
    uses(Modelica(version = "4.0.0"), Buildings(version = "12.1.0")));
end RIMAEL;
