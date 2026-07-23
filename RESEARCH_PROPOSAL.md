# Research Proposal: Event-Synchronized EEG Acquisition Using Interactive Game Paradigms

## Title

**Sheeg: A Synchronized EEG and Behavioral Event Recording Platform for Cognitive and Affective Task Research**

## Investigators

- Harpreet Singh, PhD student in Computational Behavioural Neuroscience,
  University of Lethbridge; Research Analyst/Consultant, JITDataInsights Lab Inc.
- Dr. Hardeep Ryait, Supervisor, University of Lethbridge
- Gurjit Singh, Director, JITDataInsights Lab Inc.
- OlaBola Balogun, tester
- Charandeep Singh, tester
- Kyra Thompson, game program coder

## 1. Introduction

Electroencephalography (EEG) is widely used to study human brain activity because it provides high temporal resolution and enables researchers to observe rapid neural changes during perception, attention, decision-making, and motor responses. However, EEG signals become substantially more valuable when they are recorded together with precisely timed behavioral and task-event labels. Without accurate event markers, EEG remains a stream of neural activity that is difficult to interpret in relation to what the participant was seeing, thinking, or doing at a specific moment.

The Sheeg software platform addresses this problem by combining interactive games, Lab Streaming Layer (LSL) event markers, and EEG acquisition from the CGX Quick-20 v2 system into one synchronized experimental workflow. The platform records game-generated markers and EEG simultaneously, allowing neural activity to be aligned with specific stimuli, subject responses, and task outcomes. This makes it possible to study brain-behavior relationships in a structured and reproducible way.

This proposal describes the importance of the Sheeg platform and the scientific value of its two task paradigms: a **Direction Task** and a **Continuous Obstacle-Avoidance Task**. Together, these tasks support the study of both cognitive and affective processes, including visual perception, attention, working memory, decision-making, motor planning, reaction timing, stress, and anxiety-related processing.

## 2. Problem Statement

Many behavioral experiments record response accuracy and reaction time, but they do not preserve a tightly synchronized link between those events and EEG. Likewise, EEG acquisition pipelines often capture neural signals without sufficiently rich task labels. As a result, researchers may know that neural changes occurred, but not exactly which stimulus, decision, or response the signal corresponded to.

The core problem is therefore not simply collecting EEG data, but collecting **meaningful, event-labeled EEG data**. A software platform is needed that can:

- present structured experimental tasks,
- emit precise event markers during each phase of task execution,
- record those markers alongside EEG in the same timeline, and
- preserve the resulting data for downstream analysis.

Sheeg is designed to solve this problem.

## 3. Rationale and Significance

The importance of Sheeg lies in its ability to synchronize three layers of information:

- **Stimulus events**: what the participant sees in the game,
- **Behavioral events**: what the participant predicts or how they respond,
- **Neural events**: the EEG activity recorded from the brain.

By synchronizing these layers, Sheeg transforms EEG from a generic time series into a labeled record of neural activity linked to specific task conditions. This has several scientific advantages:

- It allows EEG epochs to be segmented by stimulus type, response type, and task phase.
- It supports trial-wise comparison of correct versus incorrect responses.
- It enables analysis of pre-stimulus, stimulus-locked, and response-locked neural activity.
- It creates higher-quality datasets for cognitive neuroscience research and future machine learning models.
- It supports more reproducible experiments by automating marker generation and recording control.

The platform is therefore valuable not only as a software tool, but as an experimental framework for studying cognition, behavior, and affective state under controlled conditions.

## 4. Research Objectives

The primary objectives of the Sheeg platform are:

1. To create a synchronized EEG and game-event recording environment using CGX Quick-20 v2, LSL markers, and LabRecorder.
2. To capture precise behavioral and stimulus labels that can be aligned with neural activity.
3. To support task paradigms that probe both cognitive processing and stress-related behavioral performance.
4. To generate structured datasets suitable for neuroscience analysis and future classification or prediction models.

## 5. Software Role in the Experimental Pipeline

The Sheeg platform is not merely a game launcher; it is an orchestration system that integrates acquisition, task execution, event marking, and recording. In the experimental workflow:

- the launcher starts the acquisition and task environment,
- the game generates behaviorally meaningful events,
- the LSL bridge publishes those events as marker streams,
- the EEG system records continuous neural signals,
- LabRecorder stores EEG and marker streams in synchronized form,
- and session metadata is saved for reproducibility and analysis.

This synchronization is essential because it ensures that task phases such as stimulus presentation, subject response, and performance outcome can be matched to the corresponding EEG segments with temporal precision.

## 6. Paradigm 1: Direction Game

### 6.1 Task Description

In the Direction Game, a cartoon character begins in the center of a frame. After the session starts, the character moves randomly in one of four directions:

- left,
- right,
- up,
- down.

After the movement occurs, an orange prompt screen appears to instruct the participant to indicate the direction in which the character moved. During the task, the game produces LSL markers describing:

- the current frame or event phase,
- the direction in which the character moved,
- and the direction predicted or selected by the subject.

Simultaneously, EEG is recorded from the CGX Quick-20 v2 acquisition system.

### 6.2 Scientific Importance

This task is scientifically important because it models a full perception-to-response pipeline in a simple and controlled way. The participant must:

1. detect the visual movement,
2. encode spatial direction,
3. retain that information briefly,
4. make a decision,
5. prepare a response,
6. and execute the response.

Because the software labels each meaningful event, neural activity can be examined at multiple stages of cognitive processing rather than only at the final behavioral response.

### 6.3 Brain Functions That Can Be Studied

The Direction Game can be used to study the following brain functions:

- **Visual perception**: detecting the onset and movement of the character.
- **Visuospatial processing**: encoding directional information such as left, right, up, and down.
- **Selective and sustained attention**: maintaining focus on the task and relevant movement events.
- **Working memory**: holding the observed direction in mind until the prompt appears.
- **Decision-making**: selecting the correct direction based on perceived and remembered information.
- **Response selection**: mapping internal judgment onto an external answer.
- **Motor planning and execution**: preparing and delivering the subject's input.
- **Error monitoring**: comparing the true direction with the predicted direction and examining neural differences between correct and incorrect trials.

### 6.4 Expected Analytical Value

Because the EEG is synchronized with specific marker types, the resulting data can be segmented into:

- pre-stimulus baseline,
- movement observation period,
- prompt/decision phase,
- response execution phase,
- correct-response trials,
- incorrect-response trials.

This makes the Direction Game suitable for studying how the brain processes visual direction, maintains task information, and commits to an answer.

## 7. Paradigm 2: Continuous Obstacle-Avoidance Task

### 7.1 Task Description

The Continuous Obstacle-Avoidance Task is a time-pressured visuomotor paradigm. In this task, an animated character moves continuously while several types of hurdles appear in its path. The participant must press the spacebar at the appropriate time so that the character avoids each hurdle.

During gameplay, the system records:

- game-generated LSL markers describing key events,
- subject actions such as jump timing,
- and continuous EEG from the CGX Quick-20 v2 system.

### 7.2 Scientific Importance

This task differs from the Direction Game because it is continuous, reactive, and time-pressured. Instead of making isolated discrete judgments, the participant must maintain constant readiness, monitor incoming obstacles, predict timing, and execute rapid motor actions repeatedly.

The Continuous Obstacle-Avoidance Task is especially valuable because it introduces conditions that may increase mental workload, tension, urgency, and performance pressure. This makes it well suited for studying stress- and anxiety-related processing in addition to basic sensorimotor performance.

### 7.3 Brain Functions That Can Be Studied

The Continuous Obstacle-Avoidance Task can be used to study the following brain functions:

- **Sustained attention**: maintaining concentration across continuous gameplay.
- **Selective attention**: prioritizing relevant obstacle information.
- **Visuomotor coordination**: linking visual obstacle detection to timed movement responses.
- **Anticipation and prediction**: estimating when an obstacle will reach the critical jump point.
- **Reaction timing**: producing actions at precisely the right moment.
- **Motor preparation and execution**: repeatedly planning and initiating the jump response.
- **Response inhibition**: avoiding jumps that are too early, unnecessary, or poorly timed.
- **Cognitive load regulation**: adapting to continuous performance demands and increasing pace.
- **Performance monitoring**: adjusting behavior after errors, missed jumps, or near failures.

### 7.4 Stress and Anxiety Relevance

The Continuous Obstacle-Avoidance Task is especially relevant for studying stress and anxiety because it can evoke:

- performance pressure,
- anticipatory tension,
- error-related concern,
- repeated urgency,
- and increased arousal during obstacle approach.

If task difficulty, speed, or obstacle density are manipulated experimentally, the paradigm can be used to examine how stress-like states affect attention, timing, and motor performance. In this context, Sheeg provides a practical framework for observing the neural correlates of stress-sensitive behavior in a controlled but engaging task environment.

## 8. Why Both Games Matter Together

The two paradigms are complementary and increase the overall research value of the platform.

The **Direction Game** is:

- structured,
- trial-based,
- and well suited for controlled cognitive analysis.

The **Continuous Obstacle-Avoidance Task** is:

- continuous,
- dynamic,
- and well suited for performance, stress, and action-under-pressure analysis.

Together, these tasks allow Sheeg to support a broader range of experimental questions:

- perception and spatial judgment,
- memory-guided decision-making,
- motor preparation and execution,
- continuous attentional control,
- stress-sensitive performance,
- and anxiety-related behavioral regulation.

This makes the software adaptable to both cognitive neuroscience and affective neuroscience use cases.

## 9. Expected Outcomes

The expected outcomes of using Sheeg include:

- synchronized EEG and marker datasets with precise event timing,
- cleaner segmentation of neural activity by task condition,
- better analysis of subject-specific cognitive and affective responses,
- improved reproducibility across sessions,
- and a foundation for future classification models using EEG and behavioral labels.

Over time, the data collected through Sheeg may support research into:

- neural signatures of direction perception,
- decision confidence and correctness,
- reaction timing under pressure,
- stress-related modulation of performance,
- and individualized patterns of cognitive control and emotional regulation.

## 10. Conclusion

Sheeg is important because it provides a synchronized brain-behavior recording platform rather than a standalone game or standalone EEG capture tool. Its real contribution is the integration of interactive task design, event labeling, and neural acquisition into one reproducible workflow.

By combining EEG from the CGX Quick-20 v2 system with real-time LSL markers from game events, the software makes it possible to study not only whether neural changes occur, but **what those neural changes correspond to in the participant's experience and behavior**.

The Direction Task enables the study of visual perception, visuospatial encoding, working memory, attention, decision-making, and error monitoring. The Continuous Obstacle-Avoidance Task enables the study of sustained attention, visuomotor coordination, prediction, motor timing, stress, and anxiety-related performance effects. Together, they make Sheeg a useful platform for cognitive and affective neuroscience research, experimental software development, and future EEG-based analytical modeling.
