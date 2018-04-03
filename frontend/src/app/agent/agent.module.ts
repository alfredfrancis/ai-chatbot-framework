import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { FlexLayoutModule } from '@angular/flex-layout';

import { AgentRoutingModule } from './agent-routing.module';
import { IntentsComponent } from './intents/intents.component';
import {CoreService} from '../services/core.service'

/* Material UI imports begins here */
import {MatIconModule,MatCardModule,MatInputModule,
MatOptionModule,MatSelectModule,MatCheckboxModule,MatButtonModule} from '@angular/material';
import {MatGridListModule} from '@angular/material/grid-list';
import {MatDividerModule} from '@angular/material/divider';
/* Material UI imports ends here */


/* Services imports begins here */
import { IntentService } from '../services/intent.service';
import {TrainingService} from '../services/training.service'
import {IntentResolverService} from '../services/intent-resolver.service';
import {ChatService} from '../services/chat.service'

import { SettingsComponent } from './settings/settings.component';
import { ChatComponent } from './chat/chat.component'
import { IntentComponent } from './intent/intent.component';
import { TrainComponent } from './train/train.component';

@NgModule({
  imports: [
    CommonModule,
    ReactiveFormsModule,
    HttpClientModule,
    FormsModule,
    FlexLayoutModule,
    
    AgentRoutingModule,
    
    MatIconModule,
    MatCardModule,
    MatInputModule,
    MatOptionModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule,
    MatGridListModule,
    MatDividerModule

  ],
  declarations: [IntentsComponent, IntentComponent, TrainComponent, SettingsComponent, ChatComponent],
  providers:[IntentService,CoreService,IntentResolverService,TrainingService,ChatService]
})
export class AgentModule { }
